# InboxPilot: Email & Document Ops Agent

> **Live Demo:** `https://inboxpilot-demo.onrender.com` | **Demo Token:** `demo-secret-token-2025` *(Header: `X-Demo-Token`)* | **Interactive Docs:** `https://inboxpilot-demo.onrender.com/docs`

[![CI & Evals](https://github.com/om3105/inboxpilot/actions/workflows/evals.yml/badge.svg)](https://github.com/om3105/inboxpilot/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.14-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.143.0-009688.svg)](https://fastapi.tiangolo.com)
[![MongoDB Atlas](https://img.shields.io/badge/MongoDB_Atlas-Checkpointer-green.svg)](https://www.mongodb.com/atlas)
[![Langfuse](https://img.shields.io/badge/Observability-Langfuse_v4-purple.svg)](https://langfuse.com)

**InboxPilot** is an autonomous, human-in-the-loop Agentic AI operations system. It ingests inbound enterprise emails and documents (leave requests, invoices, support tickets), extracts typed Pydantic entities, performs verified cross-checks in MongoDB Atlas, drafts contextual replies, and proposes database mutations.

Crucially, **any high-risk write action is gated behind a persistent human approval interrupt**. Paused threads are persisted in MongoDB Atlas using LangGraph checkpointing, allowing state to survive container redeployments and cloud cold restarts on Render.

---

## 🏛️ System Architecture

```mermaid
graph TD
    Inbound([Inbound Document / Email / PDF]) --> Classify[1. Classify & Extract: Gemini LLM + Pydantic]
    Classify --> Lookup[2. Record Lookup: MongoDB Atlas / MCP]
    Lookup --> Decide{3. Decision Engine}
    
    Decide -->|Unknown / Injection / Missing ID / Discrepancy| DeadLetter[Needs Human Review State]
    Decide -->|Record Verified| Draft[4. Draft Response Generator]
    
    Draft --> Gate{5. Human Approval Gate: LangGraph interrupt}
    
    Gate -->|No Mutation Needed| Complete([Completed Run])
    Gate -->|Mutation Required: Leave / Invoice / Ticket| Paused[Thread Paused & Checkpointed in MongoDB]
    
    Paused --> API[Human Decision via POST /runs/:id/approve or reject]
    
    API -->|Approved| Exec[6. Execute Mutation: apply_update]
    API -->|Rejected| Reject[Mark State Rejected]
    
    Exec --> Complete
    Reject --> Complete
    DeadLetter --> Complete
```

---

## 📊 Evaluation & Benchmark Results

Evaluated against a curated 50-example labelled benchmark (`evals/dataset.json`) covering standard traffic, missing fields, ambiguous wording, out-of-range balances, irrelevant mail, and adversarial prompt-injection attempts. Every metric is scored strictly per case, and the runner prints each failing case with the reason.

**Offline mode** (deterministic heuristic extractor, no API key; this is what CI runs as a regression gate, not a measure of LLM quality):

| Metric | Score | What it checks |
|:-------|:-----:|:---------------|
| **Classification Accuracy** | **92.0%** | `document_type` matches the label |
| **Tool-Selection Accuracy** | **100.0%** | Tool trace matches the expected sequence exactly |
| **Field-Extraction Accuracy** | **100.0%** | Each labelled field (IDs, leave type, …) |
| **Decision Accuracy** | **100.0%** | Proposed write, or safe no-op / human review, matches the label |
| **Heuristic Draft Score** | **87.3%** | Rule-based tone, grounding, and injection-leak check (not an LLM judge) |

Known offline failures (4): ambiguous wording without keywords ("Need time off next month") is classified `unknown` by the offline heuristic, and one role-play injection is classified as an invoice. All four still route safely to human review: unclassifiable mail and inputs matching prompt-injection patterns never get an automated write or reply.

**Live mode** (real LLM calls, `nvidia/nemotron-3-ultra-550b-a55b` via the NVIDIA API catalog; all 50 cases answered live, 0 heuristic fallbacks; raw per-case results in `evals/live_cache.json`):

| Metric | Score |
|:-------|:-----:|
| **Classification Accuracy** | **96.0%** |
| **Tool-Selection Accuracy** | **100.0%** |
| **Field-Extraction Accuracy** | **100.0%** |
| **Decision Accuracy** | **100.0%** |
| **Heuristic Draft Score** | **90.0%** |

Live failures (2): "Please send money for that service as discussed" is classified as an invoice (labelled `unknown`), and a SQL-injection email is classified `unknown` (labelled invoice). Both still route to human review. The grounding check discarded 5 hallucinated identifiers (e.g. `EMP-001` where the text had none) before they could reach a lookup.

The first live run scored 66% classification / 74% decisions. The cause was ours, not the model's: with every schema field optional, the model omitted keys, which silently defaulted (`document_type` became `unknown`). The LLM now gets a schema where every field is required but nullable.

To reproduce, set an API key and run:

```bash
# NVIDIA only (what the table above used)
LLM_PROVIDERS=nvidia LLM_MAX_RPM=30 python -m evals.runner --cache evals/live_cache.json

# Gemini free tier (5 req/min, 20 req/day per model): throttle, use template drafts,
# and resume across days from the cache.
LLM_PROVIDERS=gemini LLM_MAX_RPM=4 LLM_LIVE_DRAFTS=false python -m evals.runner --cache evals/live_cache.json
```

If every provider fails on a case (quota or outage), the run stops there instead of scoring a heuristic fallback, so partial results are always genuinely live and clearly marked `PARTIAL`.

### LLM provider fallback
Calls try providers in `LLM_PROVIDERS` order (default `gemini,nvidia`), then the offline heuristic. Transient errors are retried; a rate-limited provider is skipped for a cooldown (1 hour after a daily-quota error) so later calls go straight to the next one.

### Benchmark Comparison: Native Tool vs MCP Server
`tools/mcp_server.py` exposes record lookups as an MCP tool over the stdio transport (JSON-RPC 2.0 with the `initialize` handshake, `tools/list`, `tools/call`). `tools/mcp_client.py` spawns it as a subprocess, so every MCP lookup crosses a real process and protocol boundary. Both paths share the same lookup backend, so the comparison isolates protocol cost:

| Metric (40 lookups) | Native (in-process) | MCP (stdio JSON-RPC) |
|:--------------------|:-------------------:|:--------------------:|
| **Result agreement** | baseline | **100%** |
| **p50 latency / lookup** | ~25 ms | ~24 ms |
| **One-time server startup** | none | ~170 ms |

Per-lookup latency is dominated by the backend (local run, Atlas unreachable, falling back to seed data), so the JSON-RPC round trip adds no measurable per-call overhead; the cost of MCP is the one-time process spawn and handshake.

---

## 📂 Repository Structure

```text
├── app/
│   ├── config.py         # Type-safe settings via pydantic-settings
│   ├── database.py       # Motor async connection pooling for FastAPI
│   ├── llm.py            # Thin LLM provider (Gemini + offline fallback)
│   ├── models.py         # Pydantic domain models & AgentState TypedDict
│   ├── telemetry.py      # Langfuse v4 OpenTelemetry instrumentation
│   └── main.py           # FastAPI routes, rate limiter, auth, & lifespan
├── agent/
│   ├── graph.py          # LangGraph state machine, interrupt() gate, routing
│   └── checkpointer.py   # MongoDBSaver checkpointer factory with MemorySaver fallback
├── tools/
│   ├── read_email.py     # .eml / plain text parser
│   ├── read_pdf.py       # PDF text extractor via pdfplumber
│   ├── extract_fields.py # LLM extraction with exponential backoff
│   ├── lookup_record.py  # MongoDB Atlas read queries
│   ├── draft_reply.py    # LLM operational response drafter
│   ├── apply_update.py   # High-risk write tool (requires human sign-off)
│   ├── mcp_server.py     # MCP stdio server (JSON-RPC 2.0)
│   └── mcp_client.py     # MCP stdio client (spawns the server)
├── evals/
│   ├── dataset.json      # 50 labelled examples & edge cases
│   ├── runner.py         # Strict per-case scoring + failure report
│   └── compare_mcp.py    # Native DB vs MCP comparative benchmark
├── tests/
│   ├── test_models.py    # Domain model validation & serialization tests
│   ├── test_tools.py     # Unit tests for all 6 tools
│   ├── test_agent.py     # LangGraph workflow, pause, & resume tests
│   ├── test_api.py       # FastAPI endpoint & auth header integration tests
│   └── test_evals.py     # Pytest regression suite enforcing metric thresholds
├── samples/              # Preloaded sample files (.eml, .txt)
├── scripts/
│   ├── seed_db.py        # Idempotent MongoDB seeder (30 mock business records)
│   └── generate_eval_dataset.py # Eval dataset generation script
├── docs/
│   └── demo_video_script.md # 2-minute portfolio video script
├── Dockerfile            # Production multi-stage Docker container
├── render.yaml           # Infrastructure-as-code for Render deployment
└── requirements.txt      # Strictly pinned dependencies
```

---

## 🛠️ Quickstart & Local Setup

### 1. Clone & Set Up Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Secrets
```bash
cp .env.example .env
```
Populate `.env` with your keys:
- `GEMINI_API_KEY`: Google Gemini API key (or leave blank to use the deterministic offline mock provider)
- `MONGODB_URI`: MongoDB Atlas connection string
- `DEMO_TOKEN`: Any secret string (e.g., `demo-secret-token-2025`)
- `LANGFUSE_PUBLIC_KEY` & `LANGFUSE_SECRET_KEY`: (Optional) Langfuse credentials

### 3. Seed Mock Enterprise Data
Loads 30 realistic mock documents into `employees`, `invoices`, and `tickets` with unique indexes:
```bash
python -m scripts.seed_db
```

### 4. Run Test Suite & Benchmark
```bash
# Run all unit and integration tests
pytest tests/ -v

# Run 50-case benchmark evaluation
python -m evals.runner

# Run MCP comparative benchmark
python -m evals.compare_mcp
```

### 5. Launch Local API Server
```bash
uvicorn app.main:app --reload --port 8000
```
Visit Swagger UI at: `http://localhost:8000/docs`.

---

## 🚢 Render Deployment Guide

### Deployment Configuration
The repository includes `render.yaml` and a `Dockerfile`.

1. **Create Web Service on Render:**
   - Connect your GitHub repository to Render.
   - Choose **Web Service** or use Render's Blueprint (`render.yaml`).
   - Runtime: `Docker` or `Python 3.11`.
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

2. **MongoDB Atlas Network Access (Critical):**
   - In MongoDB Atlas, navigate to **Network Access** → **IP Access List**.
   - Click **Add IP Address** → Choose **Allow Access from Anywhere (`0.0.0.0/0`)** because Render assigns dynamic outbound IP addresses on free and starter tiers.

3. **Set Environment Variables on Render Dashboard:**
   - `GEMINI_API_KEY`
   - `MONGODB_URI`
   - `MONGODB_DB_NAME` = `inboxpilot`
   - `DEMO_TOKEN` = `demo-secret-token-2025`
   - `LANGFUSE_PUBLIC_KEY` & `LANGFUSE_SECRET_KEY`

> **Note on Render Free Tier Cold Starts:** Free tier services spin down after 15 minutes of inactivity. The initial request may take ~45–50 seconds to warm up the container. Subsequent requests execute in < 400ms.

### Post-Deploy Verification Checklist
- [ ] Call `GET /health` → returns `{"status": "healthy"}`.
- [ ] Call `GET /samples` → returns preloaded mock documents.
- [ ] Call `POST /process` with header `X-Demo-Token` → confirms agent extracts fields and returns `status: "awaiting_approval"`, `requires_approval: true`.
- [ ] Call `POST /runs/{run_id}/approve` → confirms LangGraph thread resumes and mutates the database.
- [ ] Check Langfuse Dashboard → confirms trace arrived with token usage and latency.

---

## 💡 Key Design Decisions & Interview Explanations

1. **Why LangGraph for Agent Orchestration?**
   * *Interview Answer:* Autonomous enterprise ops require deterministic state boundaries and human oversight. ReAct loops often suffer from non-deterministic looping or accidental writes. LangGraph provides an explicit cyclic state machine with first-class state checkpointing and native `interrupt()` points that pause execution without blocking web worker threads.
2. **Why MongoDB Atlas for Checkpointing?**
   * *Interview Answer:* Platforms like Render have ephemeral filesystems—any in-memory or SQLite checkpointer is wiped when a container restarts or deploys. Storing LangGraph checkpoints in MongoDB Atlas ensures that human-in-the-loop approval threads survive container crashes, restarts, and redeployments.
3. **How does the system prevent Hallucinated Actions & Injections?**
   * *Interview Answer:* We employ strict Pydantic models for domain outputs. If an extraction fails schema constraints or an adversarial prompt injection is detected, the agent routes to a `needs_human_review` fallback state. Furthermore, high-risk tools cannot execute autonomously; they require an explicit cryptographic or authenticated approval command via the API.
4. **Why Model Context Protocol (MCP)?**
   * *Interview Answer:* MCP decouples internal database logic from the AI agent. Instead of hardcoding proprietary database clients into agent nodes, exposing tools via MCP JSON-RPC allows any external agent runtime to safely interact with our enterprise data under standardized capability schemas.

---

## ⚠️ Known Limitations
1. **Scanned PDF Documents:** The current parser uses `pdfplumber`, which extracts programmatic digital text. Scanned raster image PDFs require an upstream OCR engine (e.g. Tesseract or Google Cloud Document AI).
2. **Free-Tier Host Latency:** Render free-tier instances sleep when idle. Cold boots incur a 45–50s delay on first invocation.
