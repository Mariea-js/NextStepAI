import asyncio
import logging
import re
from datetime import datetime, timezone
from time import perf_counter

from .chunker import chunk_text
from .content_extractor import extract, validate_evidence_text
from .embeddings import EmbeddingService
from .gap_engine import profile_gaps
from .llm_client import LLMClient, LLMError
from .member_a_client import MemberAClient, MemberAError, top_three_eligible
from .models import AnalysisResponse, DocumentChecklist, EvidenceItem, ExplanationOutput, LLMStatus, Recommendation, Roadmap, RoadmapItem, StudentProfile
from .profile_analyzer import deterministic_profile_observations
from .prompt_builder import recommendation_prompt
from .source_fetcher import SourceFetcher
from .vector_store import VectorChunk, VectorStore

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.INFO)

_DOCUMENT_PATTERNS = (
    (re.compile(r'\bacademic transcripts?\b', re.I), 'Academic transcripts'),
    (re.compile(r'\b(?:cv|resume)\b', re.I), 'CV or resume'),
    (re.compile(r'\bpersonal statement\b|\bstatement of purpose\b|\bmotivation letter\b', re.I), 'Personal statement or statement of purpose'),
    (re.compile(r'\brecommendation letters?\b|\breference letters?\b', re.I), 'Recommendation or reference letters'),
    (re.compile(r'\bpassport(?: copy)?\b', re.I), 'Passport or passport copy'),
    (re.compile(r'\b(?:degree|enrollment|language) certificates?\b', re.I), 'Relevant certificates'),
)
_REQUIREMENT_SIGNAL = re.compile(r'\brequire(?:d|ment)?\b|\bmust submit\b|\bsubmit\b|\bupload\b|\bprovide\b', re.I)


def _document_checklist(evidence: list[EvidenceItem]) -> DocumentChecklist:
    """Extract only explicitly named documents from retrieved requirement text."""
    items: list[str] = []
    for item in evidence:
        for sentence in re.split(r'(?<=[.!?])\s+', item.excerpt):
            if not _REQUIREMENT_SIGNAL.search(sentence):
                continue
            for pattern, label in _DOCUMENT_PATTERNS:
                if pattern.search(sentence) and label not in items:
                    items.append(label)
    if not items:
        return DocumentChecklist(status='unavailable', note='Not available from the official source')
    return DocumentChecklist(status='available', items=items)


def _fallback_actions(match, evidence: list[EvidenceItem]) -> list[str]:
    actions = []
    if evidence:
        actions.append(f'Review the retrieved official guidance for {match.name} and follow only the requirements stated there.')
    else:
        actions.append(f'Open the official source for {match.name} and confirm the current application instructions.')
    if match.deadline_raw:
        actions.append(f'Use the stated deadline information ({match.deadline_raw}) to plan the application timing.')
    breakdown = match.score_breakdown or {}
    scored = [(key, value) for key, value in breakdown.items() if key != 'total_score' and isinstance(value, (int, float))]
    if scored:
        key, value = max(scored, key=lambda pair: pair[1])
        actions.append(f'Prioritize this opportunity because its strongest recorded fit is {key.replace("_", " ")} at {value:g}/100.')
    return actions


def _roadmap(recommendations: list[Recommendation], gaps, all_results) -> Roadmap:
    if recommendations:
        lead = recommendations[0]
        summary = f'Start with {lead.name}, then work through the remaining eligible opportunities in score order.'
        if gaps:
            summary += ' Address the profile gaps in parallel so they do not delay later applications.'
        steps = [RoadmapItem(priority='High', action=rec.actions[0], reason=f'{rec.name} is ranked among the eligible recommendations.', estimated_time=None) for rec in recommendations[:3]]
        for gap in gaps:
            if len(steps) >= 3:
                break
            steps.append(RoadmapItem(priority=gap.priority, action=gap.recommended_action, reason=gap.gap, estimated_time=gap.estimated_time))
        return Roadmap(summary=summary, steps=steps)

    summary = 'No Eligible opportunities were returned for this profile. Work through the identified gaps, then reassess the profile against the dataset.'
    steps = [RoadmapItem(priority=gap.priority, action=gap.recommended_action, reason=gap.gap, estimated_time=gap.estimated_time) for gap in gaps[:3]]
    if not steps:
        partials = [r for r in all_results if r.eligibility_status == 'Partial Match']
        if partials:
            reason = partials[0].reasons_failed[0] if partials[0].reasons_failed else 'Partial Match retained as context.'
            steps.append(RoadmapItem(priority='Medium', action=f'Review the failed eligibility criteria for {partials[0].name} before the next matching run.', reason=reason, estimated_time=None))
        else:
            steps.append(RoadmapItem(priority='Medium', action='Review the profile fields and official opportunity criteria before running the match again.', reason='No eligible or partial matches were returned.', estimated_time=None))
    return Roadmap(summary=summary, steps=steps)


class AnalysisService:
    def __init__(self, member_a: MemberAClient, fetcher: SourceFetcher, registry, store: VectorStore, embeddings: EmbeddingService, llm: LLMClient):
        self.member_a, self.fetcher, self.registry, self.store, self.embeddings, self.llm = member_a, fetcher, registry, store, embeddings, llm

    async def ingest(self, opp_id: int, name: str, url: str) -> str | None:
        started = perf_counter()
        try:
            fetch_started = perf_counter()
            fetched = await self.fetcher.fetch(url)
            logger.info('timing stage=source_fetch opportunity=%s duration_ms=%.1f', opp_id, (perf_counter() - fetch_started) * 1000)
            extract_started = perf_counter()
            text, typ = extract(fetched)
            validate_evidence_text(text, fetched.url, name)
            logger.info('timing stage=source_extract opportunity=%s duration_ms=%.1f', opp_id, (perf_counter() - extract_started) * 1000)
            if len(text) < 80:
                self.registry.record(opp_id, name, url, typ, None, 'unavailable', 'partial', 'too little extractable text')
                return 'Official source had too little extractable text.'
            record, changed = self.registry.record(opp_id, name, fetched.url, typ, text)
            if changed:
                pieces = chunk_text(text)
                vectors = self.embeddings.embed_texts(pieces)
                now = datetime.now(timezone.utc)
                self.store.add([VectorChunk(f'{opp_id}:{record.source_version}:{i}', piece, vector, {'opportunity_id': opp_id, 'source_url': fetched.url, 'source_version': record.source_version, 'source_type': typ, 'retrieved_at': now}) for i, (piece, vector) in enumerate(zip(pieces, vectors))])
            logger.info('timing stage=source_ingest opportunity=%s duration_ms=%.1f', opp_id, (perf_counter() - started) * 1000)
            return None
        except Exception as exc:
            self.registry.record(opp_id, name, url, 'pdf' if url.lower().endswith('.pdf') else 'html', None, 'error', 'failed', str(exc))
            return f'Official source unavailable for {name}: {exc}'

    async def _analyze_match(self, profile: StudentProfile, match, gaps):
        started = perf_counter()
        limitations: list[str] = []
        evidence: list[EvidenceItem] = []
        if not match.source_url:
            limitations.append(f'Member A did not provide an official source URL for {match.name}.')
        else:
            issue = await self.ingest(match.opportunity_id, match.name, match.source_url)
            if issue:
                limitations.append(issue)
            else:
                from .retriever import Retriever
                retrieve_started = perf_counter()
                evidence = Retriever(self.store, self.embeddings, self.registry).retrieve(match.opportunity_id, match.name + ' eligibility requirements IELTS TOEFL English proficiency publications academic qualifications application documents deadlines', 6)
                logger.info('timing stage=evidence_retrieval opportunity=%s duration_ms=%.1f chunks=%s', match.opportunity_id, (perf_counter() - retrieve_started) * 1000, len(evidence))
                if not evidence:
                    limitations.append(f'Insufficient retrieved evidence for {match.name}; no source-specific details are asserted.')

        why = 'Member A classified this opportunity as Eligible and ranked it using the deterministic score shown separately.'
        actions = _fallback_actions(match, evidence)
        calls_attempted = 0
        calls_succeeded = 0
        llm_reason = 'not_attempted'
        if evidence:
            try:
                calls_attempted = 1
                llm_started = perf_counter()
                generated = await self.llm.generate_json(recommendation_prompt(profile, match, evidence, [gap.gap for gap in gaps]))
                logger.info('timing stage=llm_call opportunity=%s duration_ms=%.1f', match.opportunity_id, (perf_counter() - llm_started) * 1000)
                validated = ExplanationOutput.model_validate(generated)
                why, actions = validated.why_this_match, validated.actions
                calls_succeeded = 1
                llm_reason = 'success'
            except LLMError as exc:
                logger.info('timing stage=llm_call opportunity=%s duration_ms=%.1f status=error', match.opportunity_id, (perf_counter() - llm_started) * 1000)
                llm_reason = exc.code
                limitations.append(f'AI explanation unavailable for {match.name}: {exc}')
            except Exception as exc:
                logger.info('timing stage=llm_call opportunity=%s duration_ms=%.1f status=invalid_output', match.opportunity_id, (perf_counter() - llm_started) * 1000)
                logger.error('Gemini structured output validation failed: %s: %s', type(exc).__name__, exc)
                llm_reason = 'invalid_output'
                limitations.append(f'Invalid AI JSON for {match.name}: {exc}')
        else:
            llm_reason = 'no_retrieved_evidence'

        recommendation = Recommendation(
            opportunity_id=match.opportunity_id,
            name=match.name,
            eligibility_status=match.eligibility_status,
            score=match.total_score,
            score_breakdown=match.score_breakdown,
            why_this_match=why,
            deadline=match.deadline_raw,
            document_checklist=_document_checklist(evidence),
            evidence=evidence,
            actions=actions or _fallback_actions(match, evidence),
        )
        logger.info('timing stage=opportunity_pipeline opportunity=%s duration_ms=%.1f', match.opportunity_id, (perf_counter() - started) * 1000)
        return recommendation, evidence, limitations, calls_attempted, calls_succeeded, llm_reason

    async def analyze(self, profile: StudentProfile) -> AnalysisResponse:
        request_started = perf_counter()
        logger.info('timing stage=profile_processing duration_ms=0.0')
        member_a_started = perf_counter()
        try:
            all_results = await self.member_a.match(profile)
        except MemberAError:
            raise
        logger.info('timing stage=member_a_match duration_ms=%.1f result_count=%s', (perf_counter() - member_a_started) * 1000, len(all_results))

        selected = top_three_eligible(all_results)
        logger.info('timing stage=selection duration_ms=0.0 eligible_count=%s selected_count=%s', len([result for result in all_results if result.eligibility_status == 'Eligible']), len(selected))
        profile_started = perf_counter()
        strengths, profile_observations, limitations = deterministic_profile_observations(profile, selected or all_results)
        gaps = profile_gaps(profile, [result for result in all_results if result.eligibility_status == 'Partial Match'])
        logger.info('timing stage=profile_and_gap_analysis duration_ms=%.1f', (perf_counter() - profile_started) * 1000)
        llm_status = LLMStatus(configured=bool(getattr(self.llm, 'key', None)), reason='not_attempted')
        if not selected:
            limitations.append('No eligible opportunities were found today. Partial matches are retained internally as context, not presented as eligible recommendations.')

        recommendations: list[Recommendation] = []
        sources: list[EvidenceItem] = []
        pipeline_results = await asyncio.gather(*[self._analyze_match(profile, match, gaps) for match in selected])
        for recommendation, evidence, match_limitations, calls_attempted, calls_succeeded, llm_reason in pipeline_results:
            recommendations.append(recommendation)
            sources.extend(evidence)
            limitations.extend(match_limitations)
            llm_status.calls_attempted += calls_attempted
            llm_status.calls_succeeded += calls_succeeded
            if llm_reason != 'not_attempted':
                llm_status.reason = llm_reason

        result = AnalysisResponse(
            profile_summary=f'This profile represents a {profile.degree_level} applicant in {profile.field} with a reported academic result of {profile.gpa_or_percentage:g}.' + (f' Target countries are {", ".join(profile.target_countries)}.' if profile.target_countries else ' No target countries were specified.'),
            strengths=strengths,
            gaps=gaps,
            roadmap=_roadmap(recommendations, gaps, all_results),
            recommendations=recommendations,
            limitations=list(dict.fromkeys(limitations + profile_observations)),
            sources=list({(item.source_url, item.source_version, item.chunk_id): item for item in sources}.values()),
            llm_status=llm_status,
            profile=profile,
            match_results=all_results,
        )
        logger.info('timing stage=response_assembly duration_ms=%.1f', (perf_counter() - request_started) * 1000)
        return result
