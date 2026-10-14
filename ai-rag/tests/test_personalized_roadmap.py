import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.models import (
    AnalysisResponse, DocumentChecklist, EvidenceItem, GapItem, LLMStatus,
    MatchResult, Recommendation, Roadmap, StudentProfile,
)
from app.presentation import format_analysis_response


def profile(test_status=None):
    return StudentProfile(
        gpa_or_percentage=3.4, field="Computer Science", degree_level="Masters",
        domicile_province="Punjab", income_bracket="Middle",
        english_test_status=test_status,
    )


def build(profile_value, evidence_text="", partial=False):
    match = MatchResult(
        opportunity_id=1, name="Research Scholarship", eligibility_status="Eligible",
        total_score=90, deadline_raw="December 2026",
    )
    evidence = [EvidenceItem(
        source_url="https://example.org/scholarship", source_version=1,
        retrieved_at=datetime.now(timezone.utc), excerpt=evidence_text,
    )] if evidence_text else []
    rec = Recommendation(
        opportunity_id=1, name=match.name, eligibility_status="Eligible", score=90,
        score_breakdown={}, why_this_match="Research alignment.",
        deadline=match.deadline_raw, document_checklist=DocumentChecklist(status="unavailable"),
        evidence=evidence, actions=["Draft a research statement aligned with the program."],
    )
    matches = [match]
    if partial:
        matches.append(MatchResult(
            opportunity_id=2, name="Competitive Scholarship",
            eligibility_status="Partial Match", total_score=95,
            reasons_failed=["CGPA below minimum (3.4 < 3.8)"],
        ))
    return AnalysisResponse(
        profile_summary="Student profile", profile=profile_value,
        recommendations=[rec], match_results=matches, roadmap=Roadmap(summary="Plan"),
        llm_status=LLMStatus(configured=False),
    )


def test_roadmap_keeps_specific_actions_even_when_eligible():
    output = format_analysis_response(build(profile()))
    actions = [step.action for step in output.application_roadmap]
    assert any("research statement" in action for action in actions)
    assert any("deadline" in action for action in actions)


def test_language_requirement_is_conditional_on_evidence():
    without = format_analysis_response(build(profile()))
    assert not any("Official source mentions a language requirement" in step.action
                   for step in without.application_roadmap)
    with_evidence = format_analysis_response(build(
        profile(), "Applicants must submit IELTS English language proficiency scores."
    ))
    assert any("Official source mentions a language requirement" in step.action
               for step in with_evidence.application_roadmap)


def test_partial_mismatch_is_visible_alongside_eligible_recommendation():
    output = format_analysis_response(build(profile("IELTS completed"), partial=True))
    assert any("CGPA below minimum" in step.action for step in output.application_roadmap)


def test_publication_requirement_not_assumed_without_source():
    output = format_analysis_response(build(profile()))
    assert not any("Official source mentions research publications" in step.action
                   for step in output.application_roadmap)
