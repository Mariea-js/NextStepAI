# NextStep AI 2.0 — Product Vision and Architecture Proposal

**Status:** Design draft — four product decisions confirmed; remaining questions pending approval.  
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

### Three readiness outcomes (roadmaps only for backend-Eligible opportunities)
- **Ready to apply:** show document preparation, official application steps, verified deadlines and a practical sequence.
- **Promising but needs work:** for backend-Eligible opportunities, explain evidence-backed gaps and preparation actions. For Partial Match opportunities, display the existing match explanation without a full roadmap.
- **Not currently eligible:** retain the existing matching status and failure reasons; no scholarship-specific roadmap for Partial Match or Not Eligible results.

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
Roadmap planner (backend-Eligible only; verified dates or undated actions)
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

For each **backend-Eligible opportunity selected for the roadmap**:
- Current deterministic match status and score, unchanged.
- Independent **readiness assessment**, with explicit limitations and verified/unverified flags.
- Strengths, unmet requirements, missing profile details, and structural restrictions.
- Prioritized actions: `title`, `why`, `category`, `priority`, `dependency`, `target_date` (only when verified), `source_url`, `evidence_excerpt`, `status`. Undated tasks are valid; do not invent duration estimates.
- Documents explicitly required by the official source; separately label general preparation suggestions.
- Deadline and date provenance: source-confirmed vs unverified. Display calendar dates **only when verified from an official source**; otherwise show 'Deadline not verified' and keep roadmap actions undated. Dataset-only dates must not be presented as confirmed dates.
- If official evidence reveals a mandatory requirement not met by an otherwise backend-Eligible applicant, show an explicit **readiness warning** and do not imply verified eligibility. Do not change the backend's status. For backend Partial Match / Not Eligible opportunities, preserve existing explanations but generate no new roadmap.

**Example:** If an official scholarship page explicitly requires IELTS 6.5 and the profile contains no language score, mark the language criterion `missing_information`, ask the applicant to provide an existing score or plan a test, and include a preparation step without claiming the student has failed the requirement. If publications are explicitly mandatory and the student reports none, identify the gap; do not assume a publication can be obtained before the deadline.

## 7. RAG engineering approach

1. **Safe source retrieval:** approved public HTTP(S) URLs, restricted redirects and network access, size/time limits, content-type checks and source provenance.
2. **Extraction:** HTML/PDF text, remove boilerplate, preserve relevant requirement sentences and document titles.
3. **Indexing:** replace the hash-embedding prototype with a genuine semantic embedding model; version collections when the embedding model changes.
4. **Retrieval:** use requirement-specific queries, opportunity-ID filtering, source-version filtering, and consider hybrid lexical + semantic retrieval for numeric thresholds and dates.
5. **Structured extraction:** constrained JSON output, evidence-span validation, no unsupported requirement generation.
6. **Comparison:** deterministic category-specific checks; uncertainty for ambiguous thresholds and missing fields.
7. **Planning:** generate roadmaps only for backend-Eligible opportunities, with grounded actions and source-verified calendar dates; leave undated actions undated.
8. **Presentation:** structured validated response; safe deterministic fallback when LLM or sources are unavailable.
9. **Observability:** measure fetch/extract/retrieve/generate latency and failures without logging personal profile secrets.
10. **Evaluation:** golden applicant/source cases, citation support, requirement recall/precision, gap correctness, no-hallucination tests, latency and end-to-end UI behavior.

## 8. Suggested development phases (after approval)

**Phase A — Contract and test cases:** approve product behavior, sample student profiles and official scholarship cases, JSON schemas, UI mockups and acceptance criteria.

**Phase B — Evidence foundation:** improve retrieval and extraction, semantic embeddings, requirement schema, provenance, freshness and tests.

**Phase C — Readiness engine:** implement validated structured requirement comparison and classification without changing the backend matcher.

**Phase D — Roadmap engine:** create opportunity-specific steps, sequencing, verified date handling, conditional improvements and conservative fallback.

**Phase E — Frontend integration:** add comprehensive intake fields, readiness/gap panels for backend-Eligible opportunities and actionable roadmap UI with browser-local progress state; preserve existing matching/dashboard functionality.

**Phase F — Verification:** unit/integration tests, adversarial source tests, manual end-to-end acceptance, latency/cost review and deployment guidance. Merge only after review.

## 9. Acceptance criteria

- Strong applicants receive concrete evidence-grounded application preparation steps, not generic placeholders.
- Applicants missing language information are not automatically labeled ineligible; official requirements are surfaced with evidence.
- Publication or research requirements are only asserted when supported by official sources.
- Partial or non-eligible cases retain their existing eligibility results and mismatch explanations, but do not receive a new full roadmap.
- The UI displays evidence-backed roadmap actions for backend-Eligible opportunities, including readiness warnings and profile gaps discovered by RAG.
- Calendar deadlines and target dates are displayed only with official-source verification; otherwise show 'Deadline not verified' and undated tasks.
- No AI response modifies backend score, rank or eligibility.
- The existing matching engine and unrelated frontend flows continue working.
- Roadmap progress is stored locally in the browser, namespaced by opportunity and action identity; no account system or server-side progress persistence is introduced.
- Graceful behavior when evidence, embeddings, Gemini or backend services are unavailable.
- Automated regression tests and realistic end-to-end examples pass.

## 10. Confirmed product decisions (2026-10-14)

1. **Coverage: Eligible only.** The new advisory roadmap is produced only for opportunities the existing backend marks `Eligible`. Partial Match and Not Eligible opportunities remain visible in existing results with their recorded reasons, but no full roadmap.
2. **Intake: Comprehensive.** Add a detailed student readiness profile without breaking the existing `/match` schema. Additional fields are forwarded to the RAG advisory layer.
3. **Timelines: Verified only.** Dates must be explicitly supported by current official-source evidence. No invented calendar dates, estimated completion dates, or unverified dataset dates shown as verified. When no verified deadline exists, show `Deadline not verified` and undated preparation actions.
4. **Progress: Local.** Use browser `localStorage` to save roadmap completion status; no accounts or cloud sync.

## 11. Remaining decisions before implementation

1. **Coverage cap:** Does 'eligible only' mean all eligible opportunities or only the top three currently selected by the RAG service? **Recommendation:** top three, to control retrieval latency and API cost.
2. **RAG readiness warnings:** If the backend says Eligible but official evidence reveals an unmet mandatory condition, should the UI show `Needs verification / Not application-ready` while preserving backend Eligible? **Recommendation:** yes.
3. **Comprehensive profile details:** Approve the proposed categories (language tests/scores, academic scale and qualifications, publications, research/experience, documents, target intake, constraints). Decide whether students may choose `unknown` for every new field. **Recommendation:** yes; do not block matching on incomplete optional details.
4. **Date verification policy:** Does a deadline need to appear on the scholarship's official site or official linked PDF, and what freshness window should count as current? **Recommendation:** official source only; retain retrieval timestamp and avoid presenting an undated or stale cycle as current.
5. **Progress privacy:** Browser-local progress disappears when storage is cleared and does not sync across devices. Is that acceptable? **Recommendation:** yes for this prototype, with a visible notice.
6. **Model and deployment constraints:** Confirm acceptable API spend, latency, and whether free-tier hosting must be supported. These affect semantic embeddings, caching, and source retrieval.
7. **Acceptance fixtures:** Select at least three official scholarships with representative profiles: ready, missing language information, and unmet mandatory requirement. Test evidence citation and failure behavior.

## 12. Approval gate

This document records decisions and recommendations only. **Do not edit application code until the user reviews the remaining decisions and explicitly authorizes implementation.** The previous security/roadmap draft PR remains separate and is not automatically included in this design branch.
