# NextStep AI 2.0 — Product Vision and Architecture Proposal

**Status:** Discussion draft — awaiting product-owner approval.  
**Branch:** `design/nextstep-advisor-v2`  
**Scope:** Design and documentation only. No application code changes are authorized on this branch yet.

## 1. Product vision

NextStep AI should evolve from a scholarship discovery and deterministic matching prototype into an **evidence-grounded, personalized scholarship readiness advisor**. Students should learn not only *which opportunities are promising* but *whether they are ready to apply, what remains uncertain, what is missing, and what concrete steps they can take next*.

### User journey
1. The student enters an academic, financial, language, research and application-readiness profile.
2. The existing deterministic backend evaluates the profile, preserves its scoring/eligibility behavior, and returns ranked opportunities.
3. The AI/RAG service retrieves scholarship-specific official requirements and source evidence.
4. A structured requirement extractor records each relevant criterion, mandatory/optional nature, thresholds, dates, evidence excerpts, URLs, and verification status.
5. A profile-to-requirement comparator labels each criterion **met / unmet / missing information / not applicable / unverified**. It must not treat missing information as proof of ineligibility.
6. An advisory layer synthesizes readiness, prioritizes actionable gaps, and generates a realistic scholarship-specific roadmap.
7. The frontend shows opportunities, supporting evidence, readiness details, deadlines and progress-tracked actions. A student can update profile details and rerun the assessment.

### Three outcomes
- **Ready to apply:** show document preparation, official application steps, verified deadlines and a practical sequence.
- **Promising but needs work:** explain the specific evidence-backed gaps, achievable improvements and timelines.
- **Not currently eligible:** distinguish fixable blockers from non-fixable restrictions and suggest alternative or future-intake planning.

A numerical fit score is **not** an eligibility probability. An official requirement should never be invented, and an LLM must not overwrite deterministic results.

## 2. Boundaries and ownership

**Preserve:** existing backend matching endpoints, hard-rule logic, ranking/scoring, dataset, and core working UI flows. No silent changes to the backend's definition of Eligible / Partial Match / Not Eligible.

**Change after approval:** AI/RAG service, evidence pipeline, requirements comparison, roadmap API/presentation, frontend intake and roadmap/dashboard surfaces needed to show the new advice.

**Avoid:** unrelated frontend redesign, new authentication systems, speculative funding/deadline claims, automatic applications, fabricated qualification assessments, and modifying team contributions beyond agreed integration needs.

## 3. Proposed component architecture

```text
Student intake (existing + optional readiness fields)
         |
         v
Existing FastAPI rule-based /match  [UNCHANGED]
         |
         v
Opportunity candidates and deterministic status/scores
         |
         v
RAG source discovery and retrieval (official pages / PDFs)
         |
         v
Evidence extraction, chunking, semantic retrieval, freshness metadata
         |
         v
Structured requirement extraction (source-linked JSON)
         |
         v
Profile / requirement comparison (deterministic, explainable)
         |
         v
Roadmap planner (prioritized actions, dates, blockers, unknowns)
         |
         v
Grounded LLM wording + output validation + conservative fallback
         |
         v
Frontend: scholarship readiness / gaps / evidence / roadmap
```

## 4. Profile information

Keep existing mandatory intake fields compatible with the current matching API. Consider **optional**, explicitly labeled additions:
- Language test type, overall score, subscores, completion status and expiry.
- Highest qualification, academic grading scale and current enrollment/completion status.
- Research experience, publication count and optional descriptions (not a substitute for verifying publication requirements).
- Available documents (transcripts, references, SOP, CV, passport).
- Intended intake, preparation time availability, and application constraints.

A field left blank means **unknown**; do not infer failure. Avoid collecting sensitive documents unless essential, and do not send unnecessary personal identifiers to the LLM.

## 5. Structured requirements contract (proposal)

Each extracted criterion should carry:
- `requirement_id`, `opportunity_id`, `category` (degree, grades, field, citizenship/domicile, language, publication, experience, funding, documents, deadline, other)
- `requirement_text`, `mandatory_status` (required / preferred / optional / unclear)
- `operator`, `threshold`, `unit` where applicable
- `source_url`, `evidence_excerpt`, `retrieved_at`, `source_version`
- `verification_status` (source_supported / ambiguous / unavailable)
- `applicant_status` (met / unmet / missing_information / not_applicable / unverified)
- `explanation`, `action_if_needed`

Do not let a generated requirement become an authoritative eligibility gate without explicit evidence and validation. When source content is missing or ambiguous, report uncertainty rather than asserting eligibility.

## 6. Roadmap response contract (proposal)

For each opportunity:
- Current deterministic match status and score, unchanged.
- Independent **readiness assessment**, with explicit limitations and verified/unverified flags.
- Strengths, unmet requirements, missing profile details, and structural restrictions.
- Prioritized actions: `title`, `why`, `category`, `priority`, `estimated_effort`, `dependency`, `target_date`, `source_url`, `evidence_excerpt`, `status`.
- Documents explicitly required by the official source; separately label general preparation suggestions.
- Deadline and date provenance: source-confirmed vs dataset-only vs unknown; never calculate a fabricated deadline.
- Next-best actions when not eligible and an honest warning when a blocker cannot realistically be fixed for the current cycle.

**Example:** If an official scholarship page explicitly requires IELTS 6.5 and the profile contains no language score, mark the language criterion `missing_information`, ask the applicant to provide an existing score or plan a test, and include a preparation step without claiming the student has failed the requirement. If publications are explicitly mandatory and the student reports none, identify the gap; do not assume a publication can be obtained before the deadline.

## 7. RAG engineering approach

1. **Safe source retrieval:** approved public HTTP(S) URLs, restricted redirects and network access, size/time limits, content-type checks and source provenance.
2. **Extraction:** HTML/PDF text, remove boilerplate, preserve relevant requirement sentences and document titles.
3. **Indexing:** replace the hash-embedding prototype with a genuine semantic embedding model; version collections when the embedding model changes.
4. **Retrieval:** use requirement-specific queries, opportunity-ID filtering, source-version filtering, and consider hybrid lexical + semantic retrieval for numeric thresholds and dates.
5. **Structured extraction:** constrained JSON output, evidence-span validation, no unsupported requirement generation.
6. **Comparison:** deterministic category-specific checks; uncertainty for ambiguous thresholds and missing fields.
7. **Planning:** grounded actions with deadlines only when verifiable, priorities and dependencies.
8. **Presentation:** structured validated response; safe deterministic fallback when LLM or sources are unavailable.
9. **Observability:** measure fetch/extract/retrieve/generate latency and failures without logging personal profile secrets.
10. **Evaluation:** golden applicant/source cases, citation support, requirement recall/precision, gap correctness, no-hallucination tests, latency and end-to-end UI behavior.

## 8. Suggested development phases (after approval)

**Phase A — Contract and test cases:** approve product behavior, sample student profiles and official scholarship cases, JSON schemas, UI mockups and acceptance criteria.

**Phase B — Evidence foundation:** improve retrieval and extraction, semantic embeddings, requirement schema, provenance, freshness and tests.

**Phase C — Readiness engine:** implement validated structured requirement comparison and classification without changing the backend matcher.

**Phase D — Roadmap engine:** create opportunity-specific steps, sequencing, verified date handling, conditional improvements and conservative fallback.

**Phase E — Frontend integration:** add optional intake fields, readiness/gap panels and actionable roadmap UI while preserving existing matching/dashboard functionality.

**Phase F — Verification:** unit/integration tests, adversarial source tests, manual end-to-end acceptance, latency/cost review and deployment guidance. Merge only after review.

## 9. Acceptance criteria

- Strong applicants receive concrete evidence-grounded application preparation steps, not generic placeholders.
- Applicants missing language information are not automatically labeled ineligible; official requirements are surfaced with evidence.
- Publication or research requirements are only asserted when supported by official sources.
- Partial or non-eligible cases show actual blockers and distinguish fixable versus structural mismatches.
- The UI displays roadmap actions even when eligible opportunities also exist.
- Every claimed deadline is marked as source-confirmed, dataset-only or unknown.
- No AI response modifies backend score, rank or eligibility.
- The existing matching engine and unrelated frontend flows continue working.
- Graceful behavior when evidence, embeddings, Gemini or backend services are unavailable.
- Automated regression tests and realistic end-to-end examples pass.

## 10. Decisions to confirm before coding

1. Should the roadmap cover only the top three eligible opportunities, or also a configurable number of high-fit partial/not-eligible opportunities?
2. Which optional intake fields are essential in the first release (language scores, publications, experience, documents)?
3. Should timelines be strictly date-driven when a source-confirmed deadline exists, or include explicitly labeled approximate preparation durations otherwise?
4. Should students be able to mark tasks complete and save progress locally, without adding accounts?
5. What are the acceptable model/API cost, response latency, and deployment constraints?
6. Which three real scholarship examples and student profiles should be our acceptance-test cases?

**Approval gate:** This document is a proposal, not authorization to change frontend/backend/RAG code. Reconcile these decisions and approve the specification before implementation.
