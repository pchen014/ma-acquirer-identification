# M&A Acquirer Identification Engine

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61dafb.svg)](https://react.dev)
[![Gemini](https://img.shields.io/badge/Gemini-3.8--flash-orange.svg)](https://deepmind.google/technologies/gemini/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ed.svg)](https://www.docker.com/)

An AI-powered Investment Banking Advisory Engine designed to compress a manual acquirer identification workflow into **under 60 seconds** at Managing Director (MD)-ready quality.

---

## 1. Quick Start

### Setting Your API Key
Configure `GEMINI_API_KEY` using either a `.env` file or direct terminal export (optional; if omitted, the engine automatically uses institutional rule-based deterministic fallback):

* **Method 1: Via `.env` file** (Recommended for persistent development)
  ```bash
  cp .env.example .env
  # Set GEMINI_API_KEY=your_actual_key_here inside .env
  ```

* **Method 2: Via terminal export command**
  ```bash
  export GEMINI_API_KEY="your_actual_key_here"
  ```

---

### Option A: Run via Docker
```bash
docker compose up --build
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser to access the banker dashboard.

---

### Option B: CLI Execution

To isolate dependencies and prevent local environment conflicts, create and activate a Python virtual environment:

```bash
# 1. Initialize and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Digest and incrementally aggregate historical deal records into SQLite:
python cli.py digest --csv data/raw/ma_deals_sample.csv

# 4. Run Acquirer Identification with a natural language prompt:
python cli.py recommend \
  --text "A $200M Healthcare Services company in the Southeast with 20% EBITDA margin, private" \
  --top-k 10

# 5. Or run using explicit structured parameters:
python cli.py recommend \
  --sector "Healthcare Services" \
  --size 200 \
  --geo "Southeast" \
  --margin 20 \
  --top-k 10
# (PDF pitch deck is automatically generated and saved to reports/acquirer_recommendations_<timestamp>.pdf)
```

---

### Option C: Local Development Run (Without Docker)

#### 1. Backend (Python 3.14)
```bash
# Initialize and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate      # On Windows: .venv\Scripts\activate

# Install dependencies and start server
pip install -r requirements.txt
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend (React + Vite)
In a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
Open **[http://localhost:5173](http://localhost:5173)** in your browser (proxies `/api` requests to port 8000).

---

## 2. Core Architecture & Workflow

The engine decouples **data ingestion** from **recommendation querying** to eliminate runtime deal scanning:

```
[ Raw Deals CSV ]
       │ (Filters outcome == 'Closed', deduplicates on transaction_id)
       ▼
[ Ingestion & Profile Store (SQLite Hybrid Schema) ]
       │ (Pre-aggregates multiples, sector distributions, embedded precedents)
       ▼
[ Banker Input (Free-Text or Form) ] ──► [ POST /api/recommend ]
       │
       ├─► Stage 1: Vectorized 5-Factor Scoring (< 50ms)
       │    • S_sector (30%): Dynamic domain adjacency & depth
       │    • S_size   (30%): Parameterized asymmetric deal capacity
       │    • S_strat  (20%): PE platform/bolt-on vs. Strategic expansion
       │    • S_geo    (10%): Target regional footprint alignment
       │    • S_fin    (10%): EBITDA margin match & multiple tolerance
       │
       ├─► Stage 2: Context Assembly & Risk Engine (< 20ms)
       │    • Precedent deal tables & sector benchmark multiples deltas
       │    • Deterministic Risk Rules (HSR review threshold > $133.9M, capacity ceiling, regional gap)
       │    • Deterministic Conviction Assignment (High / Medium / Low)
       │
       ├─► Stage 3: Gemini 3.8 Flash Synthesis (4–8s)
       │    • Async worker pool (asyncio.Semaphore)
       │    • Pydantic structured output (6 mandatory sections per acquirer)
       │
       └─► Stage 4: PDF Compilation & Delivery
            • ReportLab compiles strictly 1-page-per-acquirer PDF
            • Returns interactive UI cards + direct PDF download URL
```

---

## 3. The 6-Section One-Page Rationale Structure

Each candidate acquirer rationale addresses the six required investment banking elements:
1. **Acquirer Overview**: Size, dry powder, core sector focus, and historical transaction scale.
2. **Strategic Fit Thesis**: Specific thesis grounding why this target makes sense for this buyer (platform build vs. bolt-on add-on, regional density).
3. **Precedent Activity**: Concrete transaction citations from closed history (target names, EV, multiples, and deal types).
4. **Valuation Context**: Analysis of the buyer's historical EV/EBITDA median vs. sector benchmark median, pricing tolerance, and discipline.
5. **Risk Flags**: At least 2 substantiated risks (e.g. HSR statutory review $> \$133.9\text{M}$, cross-regional integration friction, leverage capacity).
6. **Conviction Level**: `High`, `Medium`, or `Low` anchored directly to data signals and deal track record.

---

## 4. Architecture Decisions & Design Rationale

### A. How We Use the Deals CSV
1. **Decoupled Ingestion & $O(K)$ Incremental Recomputation**:
   - Rather than scanning raw CSV records during live query time, incoming deals are ingested once, validated, deduplicated, and pre-aggregated into an **acquirer profile database**.
   - If a banker uploads an updated CSV, the system only recomputes metrics for the specific acquirers present in the update batch ($O(K)$ complexity rather than $O(N)$ full-store re-indexing).
2. **Strict Transaction Quality Filtering**:
   - Only records with `outcome == 'Closed'` represent completed, market-clearing transaction valuation and verified execution capability. Non-closed transactions (`Withdrawn`, `Terminated`, `Pending`) are filtered out to prevent survivorship and pricing distortion.
3. **Hybrid SQLite Schema (Queryable Columns + JSON Payloads)**:
   - Scalar 1-to-1 metrics (`total_deals_count`, `median_deal_size_mm`, `median_ev_ebitda`, `primary_sector`) are stored as indexed SQL columns for rapid SQL slicing.
   - Variable 1-to-many collections (`sector_deal_counts`, `embedded_precedents`, `tag_frequencies`) are preserved as JSON columns for instant Pydantic object rehydration without complex multi-table joins.

### B. How We Structured the LLM Prompt
1. **Role Persona & Tone**:
   - Framed as a **Senior Managing Director / Head of M&A Healthcare & Mid-Market Advisory**. Tone is strictly terse, analytical, and numbers-driven, completely barring generic sales fluff or marketing superlatives.
2. **Zero-Hallucination Grounding via Pre-Calculated Contexts**:
   - The LLM is **never asked to calculate mathematical metrics** or guess valuations. In Stage 2, Python pre-computes:
     - Exact median multiples (EV/EBITDA, EV/Revenue)
     - Multiple deltas against closed sector benchmarks (e.g., `+2.1x spread vs 13.6x sector benchmark`)
     - Filtered precedent transaction tables with verbatim target names, deal sizes, and deal types
     - Rule-based risk triggers (HSR threshold tests, leverage capacity stretch)
   - These facts are serialized into the candidate context payload passed to Gemini. The prompt strictly instructs the model to cite only verified data points present in the payload.
3. **Structured JSON Output via Pydantic Schema**:
   - The model output is strictly enforced via Gemini's `response_mime_type="application/json"` and `response_schema=AcquirerRationale`, guaranteeing valid JSON structure and exact section adherence every run.

### C. 5-Factor Scoring Model & Market Nuances
1. **70%+ Financial Sponsor (PE) Skew**:
   - Evaluates PE buyers on **Platform Build** capability ($100M–$400M) and **Bolt-on** capacity, while evaluating Corporate Strategics on clinical synergy and geographic expansion.
2. **4-Tier Adjacent Sector Graph**:
   - Overcomes thin subsector data (e.g. 46 deals in Healthcare Services) via domain adjacency: Direct Match (1.00), Tier 1 Care Delivery (0.85: Dental, Physician Groups, Home Health), Tier 2 Enablement (0.65: Health IT, RCM), Tier 3 Life Sciences (0.20).
3. **Asymmetric Deal Size Capacity ($S_{\text{size}}$)**:
   - Does not unfairly penalize multi-billion PE funds for acquiring a $200M platform, while heavily penalizing under-capitalized buyers whose maximum historical deal is below 60% of target EV.

---

## 5. Assumptions Made About Target Company & Dataset

* **Outcome Integrity**: Only `Closed` deals reflect verified financing and execution capability. Pending, Withdrawn, or Terminated deals are filtered out.
* **Sector vs. Subsector Equivalence**: In the sample dataset, `sub_sector` is identical to `sector`; redundant fields are normalized into `sector`.
* **Mandatory Identifiers**: Every valid record requires a `transaction_id`. Missing IDs are rejected; existing IDs are skipped to maintain idempotency.
* **Valuation Multiples**: Multiple fields that are empty or zero are treated as undisclosed and excluded from median calculations without distorting the median of known multiples.
* **Target Profile Baseline**: When using free-text (e.g., *"A $200M Healthcare Services company in the Southeast with 20% EBITDA margin, private"*), the engine assumes an enterprise value of $200M, private corporate ownership, and middle-market platform characteristics.

---

## 6. Known Limitations & Failure Modes

* **Sparse Deal History for Niche Buyers**: Acquirers with only 1–2 closed deals in the dataset have lower statistical confidence for standalone valuation medians. *Mitigation:* The engine incorporates broader sector benchmark medians and scales volume weight accordingly.
* **Static Point-in-Time Data**: The dataset records historical closed transactions, but does not capture real-time PE fund lifecycle stages (e.g., whether a fund's investment period has ended or if dry powder has already been deployed).
* **Unseen Sectors (Cold Start)**: Targets in sectors outside the adjacency graph receive a baseline proximity score of 0.20, falling back to deal size capacity, multiple tolerance, and geographic alignment.
* **External LLM Outages / Quota Exhaustion**:
  - *Mitigation:* Built-in **Institutional Deterministic Synthesizer Fallback** in `src/llm/gemini_client.py`. If `GEMINI_API_KEY` is omitted, offline, or rate-limited, the application seamlessly generates the complete 6-section MD rationales and PDF without throwing runtime errors.

---

## 7. What We Would Improve Given More Time

1. **End-to-End Testing & Automated Evaluation Pipeline**:
   - **Ground-Truth Benchmark Suite**: Construct an expert-curated evaluation dataset pairing real-world target profiles with verified, banker-approved buyer lists to quantitatively benchmark ranking precision.
   - **Intermediate Calculation & Aggregation Auditing**: Implement automated test suites validating the mathematical precision of each data pipeline stage—including incremental profile aggregations, percentile valuation multiples, sector benchmark deltas, and deterministic HSR/capacity risk rule triggers.
   - **Rubric-Based "LLM-as-a-Judge" Evaluation**: Deploy an independent LLM judge with structured evaluation rubrics to grade generated rationales against strict MD-readiness criteria.
2. **Dynamic Factor Weight Tuning**:
   - Expose sliders in the frontend allowing bankers to custom-weight Sector (30%), Size (30%), Strategy (20%), Geo (10%), and Financials (10%) based on specific engagement objectives.
3. **Interactive Banker Feedback & Exclusion Loop**:
   - Provide an "Exclude Acquirer" button in the web UI (e.g., *"Fund is out of investment period"*), instantly reranking remaining candidates in $< 50\text{ms}$ without re-aggregating data.
4. **Live SEC EDGAR & Web Portfolio Enrichment**:
   - Integrate automated crawlers to check current active portfolio companies and verify whether a sponsor already owns a competing platform in the target's specific state/county.

---

## 8. Handling Output Non-Determinism & Reproducibility

1. **Deterministic Stages (Stage 1 & Stage 2)**:
   - Candidate ranking ($S_{\text{sector}}, S_{\text{size}}, \dots$), conviction tier assignment (`High`, `Medium`, `Low`), and risk triggers are computed purely using deterministic Python mathematics.
   - For identical input parameters and datasets, **candidate ranking and Match Scores are 100% bit-exact across all runs**.
2. **LLM Temperature and Schema Constraints (Stage 3)**:
   - Gemini API calls enforce `temperature=0.0` along with Pydantic JSON schema validation. This minimizes token sampling variance and grounds text strictly in provided numbers.
   - *Acknowledgment of Variance:* Natural language phrasing (sentence structure and syntax) may vary slightly between LLM invocations, but all factual numbers, precedent citations, multiples spreads, and risk flags remain strictly anchored to the provided context.
3. **Offline Deterministic Fallback**:
   - For environments requiring 100% reproducible, zero-variance outputs (e.g., regression testing or CI/CD), the engine's deterministic synthesis fallback produces identical word-for-word rationales on every execution.
4. **Run Archival & Idempotency**:
   - Every execution is assigned a unique `report_id` and cached in SQLite (`recommendation_runs` table), storing the exact target profile, candidate rankings, generated rationales, and PDF path for reliable auditability.

---

## 9. Project Layout

```
ma-acquirer-identification/
├── Dockerfile                  # Multi-stage container (Node React + Python 3.14)
├── docker-compose.yml          # Container configuration with volume mounts
├── requirements.txt            # Python dependencies (FastAPI, Google GenAI, ReportLab)
├── cli.py                      # Headless CLI entrypoint (digest & recommend)
├── README.md                   # System documentation
├── data/
│   ├── raw/ma_deals_sample.csv # Uploaded and source raw deals datasets (archived for records)
│   └── store/                  # SQLite hybrid profile store (queryable columns + JSON)
├── reports/                    # Generated downloadable PDF pitch decks
├── frontend/                   # React.js application
│   └── src/
│       ├── App.jsx             # Main dashboard
│       ├── index.css           # Institutional dark-mode design system
│       └── components/         # Uploader, TargetForm, AcquirerCard
└── src/                        # Python 3.14 backend
    ├── config.py               # Weights, adjacency graph, thresholds, .env loader
    ├── schemas.py              # Pydantic models (Target, Acquirer, Rationale)
    ├── database.py             # SQLite WAL-mode hybrid store
    ├── pipeline.py             # Master orchestrator
    ├── ingestion/              # CSV validation & incremental aggregation
    ├── engine/                 # 5-factor scorer, risk rules, context assembler
    ├── llm/                    # Gemini 3.8 Flash client & prompt templates
    ├── reporting/              # ReportLab 1-page-per-acquirer PDF generator
    └── api/                    # FastAPI routes & static server
```
