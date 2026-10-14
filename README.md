# NextStep AI

> **AI-powered scholarship discovery platform for Pakistani students and global applicants.**  
> Built by a 5-member team as a capstone project in Aurattech Fellowship

NextStep AI helps Pakistani students discover scholarships they legitimately qualify for. By providing an academic and financial profile (CGPA, study discipline, domicile province, household income bracket, and country preferences), the platform instantly matches the student against **79 catalogued scholarship records**, evaluates rule-based eligibility checks, computes a weighted fit score, and enriches top opportunities with AI-driven explanations and an actionable application roadmap.

---

## 📸 Key Features

| Feature | Description |
|---|---|
| **Intake Engine** | 4-step progressive form with instant GPA/% converter and persistent `localStorage` autosave. |
| **Deterministic Matching** | Rule-based checks (CGPA, degree level, study field, domicile, income bracket and country preference); one mismatch is classified as a partial match, not verified eligibility. |
| **Multi-Dimensional Scoring** | Weighted composite score: Academic (30%), Field (20%), Funding (25%), Country (15%), Domicile (10%). |
| **Plan A / B / C Tiers** | Groups opportunities into Reach / International (Plan A), Realistic (Plan B), and Safety / Domestic (Plan C). |
| **AI Evidence Layer (RAG)** | Retrieves scholarship text via ChromaDB vector embeddings and prompts Google Gemini for grounded explanations. |
| **Currency Stress-Testing** | Real-time PKR devaluation scenarios (+0%, +15%, +30%) for tuition and living expense projections. |
| **Interactive Roadmap** | Scholarship-specific document preparation checklists (CNIC, domicile, transcripts, SOP) with progress tracking. |
| **Parent Financial Summary** | Jargon-free, printable / PDF-exportable table comparing scholarship coverage, subsidies, and family out-of-pocket costs. |

---

## 🏗️ System Architecture — 3 Components

```
                                  ┌───────────────────────────────────┐
                                  │         STUDENT BROWSER           │
                                  │      React 19 + Vite + Tailwind    │
                                  │   (Local: :5173 / Prod: Vercel)   │
                                  └───────────────┬───────────────────┘
                                                  │
                         ┌────────────────────────┴────────────────────────┐
                         │ POST /match                                     │ POST /analyze (async)
                         ▼                                                 ▼
       ┌───────────────────────────────────┐             ┌───────────────────────────────────┐
       │      BACKEND MATCHING ENGINE      │             │         AI RAG EVIDENCE LAYER     │
       │         FastAPI (port 8000)       │             │          FastAPI (port 8001)      │
       │   (Local: :8000 / Prod: Render)   │             │    (Local: :8001 / Prod: Render)  │
       └─────────────────┬─────────────────┘             └─────────────────┬─────────────────┘
                         │                                                 │
                         │                                                 │ Calls backend /match
                         ▼                                                 ▼ + scrapes scholarship URLs
       ┌───────────────────────────────────┐                               │
       │         DATA PERSISTENCE          │◄──────────────────────────────┘
       │  Primary: database/nextstepai.db  │
       │  Fallback: backend/data/*.xlsx    │
       └───────────────────────────────────┘
```

---

## 📁 Repository Structure

```
NextStepAI/
├── frontend/                     # Client application (React 19, Vite 8, Tailwind 4)
│   ├── public/logo.png           # Compass brand logo
│   ├── src/
│   │   ├── components/           # Navbar, NavTabs, Header, Toast, SkeletonLoader, Footer
│   │   ├── screens/              # 8 screens: Landing, Login, Account, Intake, Dashboard, Detail, Roadmap, ParentView
│   │   ├── api.js                # Unified HTTP adapter for Backend (:8000) & AI RAG (:8001)
│   │   ├── explain.js            # Offline rule-based explanation engine
│   │   └── constants.js          # Status styles, score breakdowns, UI badges
│   ├── vercel.json               # SPA routing rewrite rules for Vercel
│   ├── .env.example              # Frontend environment variables template
│   └── README.md                 # In-depth frontend documentation
├── backend/                      # Matching engine microservice (FastAPI, Python)
│   ├── app/
│   │   ├── main.py               # REST endpoints (/match, /opportunities/count, /admin/refresh-data)
│   │   ├── models.py             # Pydantic schemas (StudentProfile, Opportunity, MatchResult)
│   │   ├── matching.py           # Pipeline runner: loads data -> checks eligibility -> scores -> ranks
│   │   ├── eligibility.py        # 6 rule checks, including preferences and a soft income heuristic
│   │   ├── scoring.py            # 5-dimension weighted scoring math
│   │   └── data_loader.py        # SQLite loader with automatic Excel fallback
│   ├── data/
│   │   └── Pakistan_Scholarships_Research.xlsx # Source research spreadsheet (82 rows)
│   └── requirements.txt          # Python dependencies
├── ai-rag/                       # Evidence & LLM microservice (FastAPI, ChromaDB, Gemini)
│   ├── app/
│   │   ├── main.py               # /analyze REST endpoint
│   │   ├── member_a_client.py    # HTTP client talking to backend /match
│   │   ├── source_fetcher.py     # Real-time web fetcher for scholarship portals
│   │   ├── content_extractor.py  # HTML sanitization & textual extraction
│   │   ├── chunker.py            # Text chunking for embeddings
│   │   ├── vector_store.py       # ChromaDB vector store
│   │   ├── embeddings.py         # HashEmbeddingService (current lexical-hash prototype; not semantic embeddings)
│   │   ├── llm_client.py         # Google Gemini API client
│   │   ├── gap_engine.py         # Missing qualification diagnostics
│   │   └── presentation.py       # Formatter outputting FrontendAnalysisResponse
│   ├── .env.example              # RAG environment variables template
│   └── requirements.txt          # AI & vector dependencies
├── database/                     # Database schemas & migrations
│   ├── schema.sql                # Table definitions for 'opportunities' & 'students'
│   ├── import_opportunities.py   # Seeder script populating SQLite from Excel
│   └── nextstepai.db             # Generated SQLite database (79 parsed records)
└── README.md                     # Main repository guide (this file)
```

---

## ⚙️ Microservices Overview

### 1. Backend Matching Engine (`backend/`, port `8000`)
- **Framework**: FastAPI + Uvicorn
- **Core Responsibility**: Deterministic filtering and ranking. Takes `StudentProfile`, evaluates eligibility rules, calculates weighted scores, and returns sorted `MatchResult[]`.
- **Endpoints**:
  - `GET /` — Health check
  - `GET /opportunities/count` — Loaded scholarship count (dataset-dependent; count may change)
  - `POST /match` — Main pipeline receiving profile JSON, returning ranked opportunities
  - `POST /admin/refresh-data` — Clears in-memory cache and re-reads database
- **Data Loading Strategy**:
  1. Checks if `database/nextstepai.db` exists $\rightarrow$ loads structured rows.
  2. If SQLite file is absent $\rightarrow$ loads from `backend/data/Pakistan_Scholarships_Research.xlsx`.

### 2. AI RAG Evidence Layer (`ai-rag/`, port `8001`)
- **Framework**: FastAPI + ChromaDB + Google Gemini
- **Core Responsibility**: Synthesizes human-readable rationales, uncovers qualification gaps, and compiles custom roadmaps.
- **Workflow**:
  1. Calls Backend `POST /match` to retrieve top candidate scholarships.
  2. Fetches textual content from official scholarship URLs.
  3. Indexes chunks into ChromaDB vector store.
  4. Queries a configurable Google Gemini model (`LLM_MODEL`) with retrieved evidence.
  5. Outputs `FrontendAnalysisResponse` with custom advice and timeline.
- **Resilience**: Operates even without a Gemini API key by using deterministic template-driven advice when AI generation is unavailable.

### 3. Frontend Client (`frontend/`, port `5173`)
- **Framework**: React 19 + Vite 8 + Tailwind CSS 4
- **Core Responsibility**: Responsive UI, reactive state management, currency stress simulations, document progress tracking, and print-ready report generation.
- **Network Resilience**: Uses `Promise.all([fetchMatches(), fetchAnalysis().catch(() => null)])`. If the AI RAG server is offline, the UI continues functioning smoothly using rule-based reasoning from `explain.js`.

---

## 🔄 End-to-End Data Flow

```
1. Student enters name and email on prototype LoginScreen
   └─ Stored in React client state (frontend-only; no DB session).

2. Student completes 4-stage Intake form (CGPA, field, province, income, budget)
   └─ Autosaved to localStorage: "nextstep_intake_draft_v1"

3. Student clicks "Find My Scholarships"
   └─ api.js dispatches two requests in parallel:
        ├─► POST http://127.0.0.1:8000/match (Backend)
        └─► POST http://127.0.0.1:8001/analyze (AI RAG, optional)

4. Backend processes profile:
   └─ Checks 6 rule checks -> Computes 5-dimension score -> Returns MatchResult[]

5. api.js executes adaptMatch():
   └─ Enriches each result with estimated PKR financials, custom document checklists,
      deadline flags, and official links.

6. Dashboard displays cards divided into Plan A, B, and C tiers.

7. DetailScreen renders score charts, currency stress test (+0%, +15%, +30%), and AI justification.

8. RoadmapScreen tracks required documentation checklists and upcoming deadlines.

9. ParentViewScreen displays an aggregate cost comparison table with full Print/PDF export.





## Technical scope and limitations

This is a team-built fellowship capstone prototype, not a live eligibility-verification or application-submission service. The scholarship records and deadline strings may be outdated; applicants must verify requirements on official scholarship pages. An `Eligible` label means that the **encoded** rules did not flag a mismatch, not that every official requirement was checked. A `Partial Match` can include a mismatch with a mandatory requirement and must not be presented as confirmed eligibility.

The evidence layer uses a **64-dimensional deterministic hash embedding**, not a trained semantic embedding model. ChromaDB stores and retrieves these vectors, and Gemini can generate explanations when configured and evidence is available. Missing or inaccessible evidence triggers conservative fallback explanations. The frontend includes an independent offline matching fallback whose behavior is not guaranteed identical to the Python backend; results should be treated as illustrative when the backend is offline. The login screen is a client-side prototype and does not provide account authentication. Source URLs and scraped content are untrusted; this capstone is not security-audited for unrestricted public deployment.

**Team contributions:** Frontend, matching engine, data research and AI/RAG were collaborative workstreams. The AI/RAG evidence layer (`ai-rag/`) is the individual workstream highlighted in this portfolio. Other team members' code should not be represented as an individual implementation.
