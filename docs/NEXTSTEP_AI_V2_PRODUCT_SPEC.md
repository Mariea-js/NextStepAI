# NextStep AI 2.0 — Product Vision and Architecture Proposal

**Status:** Design draft — product behavior confirmed; implementation details and acceptance fixtures pending.  
**Branch:** `design/nextstep-advisor-v2`  
**Scope:** Design and documentation only. No application code changes are authorized on this branch yet. The latest clarified decisions in Section 14 take precedence if earlier draft wording conflicts.

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

### Three readiness outcomes (roadmaps for all selected opportunities)
- **Ready to apply:** show document preparation, official application steps, verified deadlines and a practical sequence.
- **Promising but needs work:** for backend-Eligible opportunities, explain evidence-backed gaps and preparation actions. For selected Partial Match opportunities, provide a realistic gap-to-eligibility roadmap explaining unmet criteria and feasible improvements.
- **Not currently eligible:** Retain the existing matching status and failure reasons. If selected among the top three, provide a realistic barrier assessment and improvement or alternative-path roadmap; never promise that structural restrictions can be fixed.

A numerical fit score is **not** an eligibility probability. An official requirement should never be invented, and an LLM must not overwrite deterministic results.

## 2. Boundaries and ownership

**Preserve:** existing backend matching endpoints, hard-rule logic, ranking/scoring, dataset, and core working UI flows. No silent changes to the backend's definition of Eligible / Partial Match / Not Eligible.

**Change after approval:** AI/RAG service, evidence pipeline, requirements comparison, roadmap API/presentation, frontend intake and roadmap/dashboard surfaces needed to show the new advice.

**Avoid:** unrelated frontend redesign, new authentication systems, speculative funding/deadline claims, automatic applications, fabricated qualification assessments, and modifying team contributions beyond agreed integration needs.

## 3. Proposed component architecture

```text
Comprehensive student intake (existing required + additional readiness fields)
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
Roadmap planner (selected top three; verified dates or undated actions)
         |
         v
Grounded LLM wording + output validation + conservative fallback
         |
         v
Frontend: scholarship readiness / gaps / evidence / roadmap
```

## 4. Profile information

**Confirmed: comprehensive intake.** Keep existing mandatory intake fields and /match request compatible; collect additional fields in a versioned advisory profile passed to RAG. New fields should be optional where unknown is a valid answer, with explicit 'not provided' states:
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

For each **selected top-three opportunity**, whether Eligible, Partial Match or Not Eligible:
- Current deterministic match status and score, unchanged.
- Independent **readiness assessment**, with explicit limitations and verified/unverified flags.
- Strengths, unmet requirements, missing profile details, and structural restrictions.
- Prioritized actions: `title`, `why`, `category`, `priority`, `dependency`, `target_date` (only when verified), `source_url`, `evidence_excerpt`, `status`. Undated tasks are valid; do not invent duration estimates.
- Documents explicitly required by the official source; separately label general preparation suggestions.
- Deadline and date provenance: source-confirmed vs unverified. Display calendar dates **only when verified from an official source**; otherwise show 'Deadline not verified' and keep roadmap actions undated. Dataset-only dates must not be presented as confirmed dates.
- If official evidence reveals a mandatory requirement not met by an otherwise backend-Eligible applicant, show an explicit **readiness warning** without altering the backend status. For selected Partial Match / Not Eligible opportunities, provide a gap-to-readiness plan where improvement is realistic; otherwise explain structural barriers and possible alternative routes.

**Example:** If an official scholarship page explicitly requires IELTS 6.5 and the profile contains no language score, mark the language criterion `missing_information`, ask the applicant to provide an existing score or plan a test, and include a preparation step without claiming the student has failed the requirement. If publications are explicitly mandatory and the student reports none, identify the gap; do not assume a publication can be obtained before the deadline.

## 7. RAG engineering approach

1. **Safe source retrieval:** approved public HTTP(S) URLs, restricted redirects and network access, size/time limits, content-type checks and source provenance.
2. **Extraction:** HTML/PDF text, remove boilerplate, preserve relevant requirement sentences and document titles.
3. **Indexing:** replace the hash-embedding prototype with a genuine semantic embedding model; version collections when the embedding model changes.
4. **Retrieval:** use requirement-specific queries, opportunity-ID filtering, source-version filtering, and consider hybrid lexical + semantic retrieval for numeric thresholds and dates.
5. **Structured extraction:** constrained JSON output, evidence-span validation, no unsupported requirement generation.
6. **Comparison:** deterministic category-specific checks; uncertainty for ambiguous thresholds and missing fields.
7. **Planning:** generate roadmaps for the selected top three across eligibility categories, with grounded actions and source-verified calendar dates; leave undated actions undated.
8. **Presentation:** structured validated response; safe deterministic fallback when LLM or sources are unavailable.
9. **Observability:** measure fetch/extract/retrieve/generate latency and failures without logging personal profile secrets.
10. **Evaluation:** golden applicant/source cases, citation support, requirement recall/precision, gap correctness, no-hallucination tests, latency and end-to-end UI behavior.

## 8. Suggested development phases (after approval)

**Phase A — Contract and test cases:** approve product behavior, sample student profiles and official scholarship cases, JSON schemas, UI mockups and acceptance criteria.

**Phase B — Evidence foundation:** improve retrieval and extraction, semantic embeddings, requirement schema, provenance, freshness and tests.

**Phase C — Readiness engine:** implement validated structured requirement comparison and classification without changing the backend matcher.

**Phase D — Roadmap engine:** create opportunity-specific steps, sequencing, verified date handling, conditional improvements and conservative fallback.

**Phase E — Frontend integration:** add comprehensive intake fields, readiness/gap panels for all selected opportunities and actionable roadmap UI with browser-local progress state; preserve existing matching/dashboard functionality.

**Phase F — Verification:** unit/integration tests, adversarial source tests, manual end-to-end acceptance, latency/cost review and deployment guidance. Merge only after review.

## 9. Acceptance criteria

- Strong applicants receive concrete evidence-grounded application preparation steps, not generic placeholders.
- Applicants missing language information are not automatically labeled ineligible; official requirements are surfaced with evidence.
- Publication or research requirements are only asserted when supported by official sources.
- Selected Partial Match / Not Eligible cases receive explicit barrier explanations and achievable gap-to-readiness roadmaps, or an honest assessment when no realistic fix exists.
- The UI displays evidence-backed roadmap actions for all three selected opportunities, including readiness warnings and profile gaps discovered by RAG.
- Calendar deadlines and target dates are displayed only with official-source verification; otherwise show 'Deadline not verified' and undated tasks.
- No AI response modifies backend score, rank or eligibility.
- The existing matching engine and unrelated frontend flows continue working.
- Roadmap progress is stored locally in the browser, namespaced by opportunity and action identity; no account system or server-side progress persistence is introduced.
- Graceful behavior when evidence, embeddings, Gemini or backend services are unavailable.
- Automated regression tests and realistic end-to-end examples pass.

## 10. Confirmed product decisions (2026-10-14)

1. **Coverage: top-three mixed shortlist.** Fill three places by priority: Eligible first, then highest-potential Partial Match, then Not Eligible if needed. Every selected opportunity receives a roadmap appropriate to its status. Do not disguise Not Eligible as a strong fit merely to fill a slot.
2. **Intake: Comprehensive.** Add a detailed student readiness profile without breaking the existing `/match` schema. Additional fields are forwarded to the RAG advisory layer.
3. **Timelines: Verified only.** Dates must be explicitly supported by current official-source evidence. No invented calendar dates, estimated completion dates, or unverified dataset dates shown as verified. When no verified deadline exists, show `Deadline not verified` and undated preparation actions.
4. **Progress: Local.** Use browser `localStorage` to save roadmap completion status; no accounts or cloud sync.

## 11. Remaining decisions before implementation

1. **Coverage cap: resolved.** Start with three opportunities; optionally expand to five later. Eligible first, then Partial Match, then Not Eligible where necessary. Preserve original labels.
2. **RAG readiness warnings: resolved.** Preserve backend Eligible and display a separate readiness warning when official evidence shows an unmet mandatory condition. Distinguish mandatory gaps, competitive enhancements, and unknown details.
3. **Comprehensive profile: resolved in principle.** Collect language tests/scores, academic scale and qualifications, publications, research/experience, documents, target intake and constraints. Unknown optional values are allowed; compare only supplied information and explicitly report uncertainty.
4. **Date verification: resolved in principle.** Use current-cycle dates explicitly supported by the official scholarship site or official linked PDF. If not verifiable, say 'Deadline not verified — check the official scholarship page'. The existing scholarship link can serve as the navigation link.
5. **Progress privacy: resolved.** Browser-local progress only; no account sync or hosting requirement.
6. **Deployment: resolved for first phase.** Local testing is sufficient; no hosting required now. Confirm the preferred Gemini/embedding provider and acceptable usage cost before implementation.
7. **Acceptance fixtures:** Select at least three official scholarships with representative profiles: ready, missing language information, and unmet mandatory requirement. Test evidence citation and failure behavior.

## 12. Approval gate

This document records decisions and recommendations only. **Do not edit application code until the user reviews the remaining decisions and explicitly authorizes implementation.** The previous security/roadmap draft PR remains separate and is not automatically included in this design branch.

## 13. Shortlist selection and roadmap policy — clarification (2026-10-14)

**Selection:** Start with three opportunities (five is a later enhancement). Prioritize backend Eligible, then Partial Match, then Not Eligible. Within each category prefer higher deterministic fit scores, but never represent a structurally ineligible opportunity as suitable. If fewer than three meaningful options exist, show fewer than three with an explanation rather than forcing unsuitable entries.

**Each selected opportunity:** Keep backend status and score untouched; separately show official-source readiness findings and a scholarship-specific roadmap. Categorize roadmap items as **mandatory requirement**, **competitive improvement**, **missing/unknown information**, or **general preparation**. For partial/ineligible results, include a feasible gap-to-readiness plan or a candid explanation of non-fixable barriers. An applicant cannot generally repair a completed-degree CGPA simply by taking a short course.

**Dates:** Use only current-cycle dates corroborated by the official scholarship page or linked official document. Otherwise show **'Deadline not verified — check the official scholarship page'**. Do not manufacture timelines, calendar targets, or duration estimates. Reuse the scholarship's existing official link in the UI.

**Profile:** Comprehensive but resilient to missing fields. Unknown is not equivalent to failing a criterion. Compare only supplied facts and source-supported requirements, and label uncertain findings.

**Progress and deployment:** Save task completion locally in the browser; no cross-device synchronization and no hosting requirement for the initial phase. Preserve the existing matching backend and working UI behavior.

**Outstanding design details before coding:** choose exact fields and validation, clarify how 'potential' is ranked within Partial Match / Not Eligible groups, decide which official sources count as current-cycle verified, and select model/cost constraints and end-to-end acceptance fixtures. No code implementation authorized yet.

## 14. Confirmed user-facing behavior and engineering review (2026-10-15)

### Selection and truthful recommendations
- Return **up to three** recommendations, with Eligible first. If fewer than three Eligible results exist, fill remaining places with **promising, realistically improvable Partial Match** results. Do not recommend Not Eligible scholarships merely to fill three slots. If no credible matches exist, display a respectful no-suitable-opportunities explanation and invite profile updates.
- A selected Partial Match receives a specific **gap-to-eligibility roadmap**: the failing rule, evidence from the official source where accessible, whether it can realistically be improved, and actionable next steps. Completed-degree CGPA, nationality or fixed residency restrictions must not be portrayed as quickly fixable. An IELTS score improvement may be feasible, but must not be guaranteed.
- If the existing backend says Eligible but an official mandatory condition is unmet, retain the backend score/status and show a **prominent, separate readiness warning**. Do not say that an applicant can safely apply despite an unresolved mandatory blocker. Distinguish required fixes, optional competitive enhancements, and unknown information.

### Official-source RAG requirements
- For each shortlisted opportunity, fetch its official scholarship page and follow relevant official linked pages/documents for eligibility, application steps, required documents, language tests and **current-cycle deadlines**. Do not assume a single homepage contains all rules. Respect link scope, crawl limits, rate limits, PDF limitations and inaccessible content; do not claim complete coverage when not achieved.
- Extract requirement text with precise source URL and supporting excerpt. Classify each criterion as mandatory, preferred, optional, unclear or not found. Compare the criterion with the student's supplied profile; never infer failure from an unknown field. An LLM may draft explanations and questions but must not invent evidence, thresholds or eligibility.
- Only display an actual deadline date if verified from the current-cycle official source. Otherwise display **'Deadline not verified — please check the official scholarship page'**. The scholarship's existing official link is sufficient; no redundant link is required in every roadmap step.
- If official retrieval fails (permissions, anti-bot restriction, timeout, parsing failure or other unknown cause), report **'Official requirements could not be verified automatically'**, rather than assuming a permissions error. Preserve clearly labeled dataset matching results, invite the student to consult the official page, and avoid source-specific claims.

### Frontend and progress
- Preserve existing layout and matching experience. Improve only comprehensive intake and the existing roadmap/assessment area with clear **Strengths**, **Requirements and gaps**, **Readiness warning**, **Roadmap**, **Deadline verification** and **Source evidence** sections.
- Unknown optional intake fields must not block matching. Store only task completion state in browser local storage, using stable identifiers; do not persist sensitive profile details unnecessarily. No hosting or account sync required for initial local testing.

### Existing code facts confirmed by read-only review of main branch
- `frontend/src/api.js` sends `POST /analyze` directly to the RAG FastAPI service and `POST /match` to the matching service; it also contains an independent client-side matching fallback with **different** scoring/eligibility behavior. The fallback must never be presented as authoritative verification.
- `ai-rag/app/main.py` exposes `POST /analyze` with a `StudentProfile` request. `ai-rag/app/member_a_client.py` calls the matching service's `POST /match`. `ai-rag/app/service.py` currently calls `top_three_eligible` and retrieves only three evidence chunks per selected eligible opportunity; this must change to support the approved mixed shortlist and broader official requirements.
- The RAG service receives scholarship source URLs in matching results and fetches them. **There is no confirmed direct RAG read of a separately stored student-profile database** in the reviewed request path; profile data is passed in the API request. Do not design against an assumed profile database until one is verified.
- The frontend contains guessed deadline placeholders, heuristic document lists, and estimated financial figures. In the enhanced advisory UI, do not present those as officially verified scholarship facts. Preserve unrelated UI flows, but distinguish legacy estimates from evidence-backed findings.

### Engineering decisions still required before implementation
1. Define comprehensive optional intake fields, normalization, validation and backward-compatible `/analyze` request/response schema.
2. Specify the **fixability policy** for Partial Match blockers and what constitutes a promising candidate; no automatic promises of eligibility.
3. Define official link-following scope, source verification/freshness, extraction fallback, request limits and caching. Some pages may be inaccessible or dynamically rendered.
4. Select local embedding/LLM provider configuration and acceptable latency/cost; create acceptance fixtures for eligible, fixable partial, structural blocker, official-page failure and deadline change.
5. Maintain the previous security/roadmap draft PR as separate work; do not silently merge it into this design branch.

**Implementation approval gate remains in force.**
