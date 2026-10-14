# NextStep AI — Member B evidence layer

Run Member A from `backend/`, then from this directory install `requirements.txt` and run `uvicorn app.main:app --reload --port 8001`. POST a `StudentProfile` to `/analyze`.

Copy `.env.example` to `.env` and place the real Gemini credential in `ai-rag/.env` as `GEMINI_API_KEY=...`. Never commit that file. `HashEmbeddingService` is a deterministic offline development/test provider; the currently wired service also uses it; no semantic provider is configured. Production retrieval would need a real semantic embedding implementation and evaluation.

The service never changes Member A. It calls `/match`, retains its complete result set, and only selects `Eligible` rows for the MVP Top 3. Scores and eligibility remain separate response fields from AI prose and retrieved evidence.

## Analysis response contract

`POST /analyze` returns the frontend presentation contract from `app/presentation.py`: `profile_summary`, up to three `top_scholarships`, `partial_matches`, and `application_roadmap`. The internal `AnalysisResponse` still carries scores, evidence, and provider diagnostics for pipeline use, but those fields are not exposed by the normal HTTP response.

`deadline` is copied from Member A's normalized `Opportunity.deadline_raw`; missing values remain `null` in the frontend response. `document_checklist` is derived only from retrieved excerpts that explicitly name documents. Otherwise it is `{ "status": "unavailable", "items": [], "note": "Not available from the official source" }`. Gemini output is validated as `why_this_match` plus a non-empty `actions` list before either is used. Gemini requests have a 30-second timeout and one short retry by default; these are configurable with `GEMINI_TIMEOUT_SECONDS` and `GEMINI_RETRY_DELAY_SECONDS`.

Gap scope is intentionally broader than the recommendation list: `gaps` may include actionable shortfalls from any `Partial Match` returned by Member A, even when three `Eligible` recommendations exist. This gives the roadmap profile-improvement context. Partial Match opportunities are never inserted into `recommendations`; that list remains the top three `Eligible` results from `top_three_eligible()`.

The presentation response shows at most five partial matches, ordered by the existing opportunity-level `total_score`. Member A computes scores for both `Eligible` and `Partial Match` opportunities; those partial scores are valid fit scores, not eligibility guarantees. If a partial result has no score breakdown, its presentation `match_score` is `null` rather than an unrelated fallback value.

Actions are requested from Gemini as opportunity-specific, evidence- and score-grounded next steps. The mocked test client intentionally returns a simple name-substituted response to exercise schema flow; it is not representative of Gemini's prose quality. The current implementation validates presence and structure, but does not semantically guarantee that two LLM action lists are meaningfully different.

## Source identity and limitations

Member A's `/match` response supplies `source_url` from the same normalized opportunity it evaluated. Member B does not read Member A's workbook. Shared URLs are fetched once per ingestion operation but chunk metadata is stamped with an opportunity ID; retrieval enforces that ID and active source version, so shared hub-page chunks cannot cross into another opportunity's evidence.

`ChromaVectorStore` uses persistent Chroma when available at `CHROMA_PATH`, while retaining an in-memory fallback for zero-service tests. No Chroma API leaks above this layer.


## Security and accuracy boundaries

Source URLs originate from the matching dataset and must be treated as untrusted input. Do not deploy the fetcher to an unrestricted network without URL allowlisting, redirect/IP safeguards, and request-size limits. The service is a capstone prototype, not a verified source of current scholarship deadlines or official eligibility decisions. Retrieved text can be stale or incomplete. The LLM receives source excerpts as untrusted data and cannot modify matching scores.
