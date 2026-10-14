import re

from pydantic import BaseModel, Field

from .gap_engine import action_for_reason
from .models import AnalysisResponse, Recommendation, StudentProfile


class ProfilePresentation(BaseModel):
    academic_profile: str
    target_countries: list[str] = Field(default_factory=list)
    budget: str | None = None
    research_summary: str


class TopScholarshipPresentation(BaseModel):
    rank: int
    name: str
    country: str | None = None
    institution: str | None = None
    eligibility: str
    match_score: float
    deadline: str | None = None
    why_suitable: str | None = None
    how_to_apply: str | None = None
    official_link: str | None = None


class PartialMatchPresentation(BaseModel):
    name: str
    country: str | None = None
    institution: str | None = None
    eligibility: str
    match_score: float | None
    deadline: str | None = None
    why_not_fully_eligible: list[str] = Field(default_factory=list)
    how_to_become_eligible: list[str] = Field(default_factory=list)
    official_link: str | None = None


class ApplicationRoadmapPresentation(BaseModel):
    priority: int
    scholarship: str
    action: str


class FrontendAnalysisResponse(BaseModel):
    profile_summary: ProfilePresentation
    top_scholarships: list[TopScholarshipPresentation] = Field(default_factory=list)
    partial_matches: list[PartialMatchPresentation] = Field(default_factory=list)
    application_roadmap: list[ApplicationRoadmapPresentation] = Field(default_factory=list)


def _deadline(value: str | None) -> str | None:
    return value or None


def _safe_why(rec: Recommendation, profile: StudentProfile) -> str | None:
    text = (rec.why_this_match or '').strip()
    sentences = re.split(r'(?<=[.!?])\s+', text)
    useful = [sentence.strip() for sentence in sentences if sentence.strip() and not any(marker in sentence.lower() for marker in ('member a', 'deterministic', 'backend', 'provider error', 'gemini', 'score', 'fit at'))]
    if useful:
        return ' '.join(useful[:2])
    if profile.field:
        return f'Aligns with your {profile.field} background and stated study preferences.'
    return 'Aligns with your stated academic profile and study preferences.'


def _how_to_apply(rec: Recommendation) -> str:
    if rec.document_checklist.status == 'available':
        return 'Review the official eligibility requirements and prepare the listed application documents.'
    return 'Review the official eligibility requirements and application instructions.'


def _research_summary(analysis: AnalysisResponse) -> str:
    profile = analysis.profile
    if profile is None:
        return 'These are the strongest scholarship opportunities identified for this profile.'
    countries = ', '.join(profile.target_countries) if profile.target_countries else 'your selected study destinations'
    budget = ' and stated funding needs' if profile.budget_pkr is not None else ''
    if analysis.recommendations:
        return f'Based on your {profile.degree_level} academic background in {profile.field}, target countries ({countries}){budget}, these are your strongest scholarship opportunities.'
    return f'Based on your {profile.degree_level} academic background in {profile.field} and target countries ({countries}), no fully eligible scholarship is currently identified; the partial matches show possible improvement paths.'


def _profile_summary(analysis: AnalysisResponse) -> ProfilePresentation:
    profile = analysis.profile
    if profile is None:
        return ProfilePresentation(academic_profile=analysis.profile_summary, research_summary=_research_summary(analysis))
    academic = f'{profile.degree_level} applicant in {profile.field} with a reported academic result of {profile.gpa_or_percentage:g}.'
    budget = f'PKR {profile.budget_pkr:,.0f}' if profile.budget_pkr is not None else None
    return ProfilePresentation(
        academic_profile=academic,
        target_countries=profile.target_countries,
        budget=budget,
        research_summary=_research_summary(analysis),
    )


def _top_scholarships(analysis: AnalysisResponse) -> list[TopScholarshipPresentation]:
    eligible = [rec for rec in analysis.recommendations if rec.eligibility_status == 'Eligible']
    return [
        TopScholarshipPresentation(
            rank=rank,
            name=rec.name,
            country=next((m.country for m in analysis.match_results if m.opportunity_id == rec.opportunity_id), None),
            institution=next((m.provider for m in analysis.match_results if m.opportunity_id == rec.opportunity_id), None),
            eligibility=rec.eligibility_status,
            match_score=rec.score,
            deadline=_deadline(rec.deadline),
            why_suitable=_safe_why(rec, analysis.profile) if analysis.profile else rec.why_this_match,
            how_to_apply=_how_to_apply(rec),
            official_link=next((m.source_url for m in analysis.match_results if m.opportunity_id == rec.opportunity_id), None),
        )
        for rank, rec in enumerate(eligible[:3], start=1)
    ]


def _partial_matches(analysis: AnalysisResponse) -> list[PartialMatchPresentation]:
    output = []
    partials = sorted(
        (match for match in analysis.match_results if match.eligibility_status == 'Partial Match'),
        key=lambda match: match.total_score if match.score_breakdown else float('-inf'),
        reverse=True,
    )[:5]
    for match in partials:
        if match.eligibility_status != 'Partial Match':
            continue
        actions = []
        for reason in match.reasons_failed:
            action = action_for_reason(reason)
            if action:
                actions.append(action[0])
        output.append(PartialMatchPresentation(
            name=match.name,
            country=match.country,
            institution=match.provider,
            eligibility='Partially matching',
            match_score=match.total_score if match.score_breakdown else None,
            deadline=_deadline(match.deadline_raw),
            why_not_fully_eligible=match.reasons_failed,
            how_to_become_eligible=list(dict.fromkeys(actions)),
            official_link=match.source_url,
        ))
    return output


def _application_roadmap(analysis: AnalysisResponse) -> list[ApplicationRoadmapPresentation]:
    """Expose evidence-backed actions and gaps, not generic one-line placeholders.

    Only retrieved evidence can establish opportunity-specific requirements.
    Missing profile fields are requests for clarification, not failed eligibility.
    """
    roadmap: list[ApplicationRoadmapPresentation] = []
    seen: set[tuple[str, str]] = set()

    def add(scholarship: str, action: str) -> None:
        action = action.strip()
        key = (scholarship, action.casefold())
        if action and key not in seen and len(roadmap) < 15:
            seen.add(key)
            roadmap.append(ApplicationRoadmapPresentation(
                priority=len(roadmap) + 1, scholarship=scholarship, action=action,
            ))

    profile = analysis.profile
    for rec in analysis.recommendations[:3]:
        # The per-scholarship LLM actions already passed through the evidence
        # pipeline. Show them instead of replacing them with generic prose.
        for action in rec.actions[:3]:
            add(rec.name, action)
        if rec.document_checklist.status == 'available':
            add(rec.name, 'Prepare the documents identified in retrieved official requirements: '
                + ', '.join(rec.document_checklist.items) + '.')
        if rec.deadline:
            add(rec.name, f'Check the official application portal for the current deadline (dataset records: {rec.deadline}); plan document preparation accordingly.')
        else:
            add(rec.name, 'Check the official portal for the current application window; no verified deadline is available in the matching data.')

        # Do not infer that an English test or publication is required merely
        # because the student has not supplied one. Look for explicit language
        # in retrieved requirement sentences before proposing gap actions.
        for item in rec.evidence:
            for sentence in re.split(r'(?<=[.!?])\\s+', item.excerpt):
                lower = sentence.lower()
                requirement = bool(re.search(r'\\b(required?|must|mandatory|eligibility|applicants? need|minimum)\\b', lower))
                if not requirement:
                    continue
                if re.search(r'\\b(ielts|toefl|english.language|language proficiency)\\b', lower):
                    status = (profile.english_test_status or '').strip().lower() if profile else ''
                    if not status or status in ('no', 'none', 'not taken', 'not yet', 'pending'):
                        add(rec.name, 'Official source mentions a language requirement. Confirm its accepted tests and minimum scores; your profile does not show a completed test.')
                if re.search(r'\\b(publications?|published research|research papers?)\\b', lower):
                    add(rec.name, 'Official source mentions research publications. Check the exact requirement and compare it with your research record; publication history was not collected in the intake profile.')

    # Preserve eligibility reasons and avoid implying that a high fit score
    # overrides a hard requirement.
    partials = sorted(
        (m for m in analysis.match_results if m.eligibility_status == 'Partial Match'),
        key=lambda m: m.total_score, reverse=True,
    )[:3]
    for match in partials:
        for reason in match.reasons_failed[:2]:
            action = action_for_reason(reason)
            if action:
                add(match.name, f'Eligibility gap: {reason}. Next step: {action[0]}')
            else:
                add(match.name, f'Eligibility mismatch: {reason}. Verify whether this requirement can be satisfied; do not assume eligibility from the fit score.')
        if match.source_url:
            add(match.name, 'Review the official scholarship requirements before investing time in an application.')

    # Missing profile fields are uncertainty, not proof of ineligibility.
    for gap in analysis.gaps[:3]:
        if gap.criterion == 'English test status':
            add('Profile readiness', 'Your language-test status is unknown. Check whether your shortlisted scholarships require a test before booking one.')
        elif gap.criterion == 'Budget':
            add('Profile readiness', 'Provide your available study budget to assess funding shortfalls; no exact funding gap can be calculated without it.')
        elif not gap.criterion.startswith('Partial Match:'):
            add('Profile readiness', gap.recommended_action)

    if not roadmap:
        add('Profile readiness', 'Review official eligibility requirements, confirm current deadlines, and update missing profile details before applying.')
    return roadmap

def format_analysis_response(analysis: AnalysisResponse) -> FrontendAnalysisResponse:
    """Convert the internal pipeline result into the stable frontend contract."""
    return FrontendAnalysisResponse(
        profile_summary=_profile_summary(analysis),
        top_scholarships=_top_scholarships(analysis),
        partial_matches=_partial_matches(analysis),
        application_roadmap=_application_roadmap(analysis),
    )
