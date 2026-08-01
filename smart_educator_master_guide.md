# 🧠 Smart-Educator — Unified Master Architecture & Execution Guide

> **The Definitive Master Report: Combining P1 (API & Data), P2 (AI & LangGraph), and P3 (Infrastructure & Fine-Tuning) Handoffs + Latest Additions**  
> **Project Version:** `v0.1.0`  
> **Target Audience:** New developers joining the project, team members reviewing system flows, or owners revising individual components.

---

## 📋 Table of Contents
1. [Project Overview & Core Objective](#-1-project-overview--core-objective)
2. [Architectural Breakdown & Team Roles](#-2-architectural-breakdown--team-roles)
3. [System Flow & Data Lifecycle](#-3-system-flow--data-lifecycle)
4. [Complete API Surface & Endpoint Reference](#-4-complete-api-surface--endpoint-reference)
5. [Database Schemas & Persistence Layer](#-5-database-schemas--persistence-layer)
6. [Caching & Vector DB Infrastructure](#-6-caching--vector-db-infrastructure)
7. [Codebase Walkthrough by Component](#-7-codebase-walkthrough-by-component)
8. [Step-by-Step Setup & How-to-Run Guide](#-8-step-by-step-setup--how-to-run-guide)
9. [Troubleshooting & Maintenance Checklist](#-9-troubleshooting--maintenance-checklist)

---

## 🚀 1. Project Overview & Core Objective

**Smart-Educator** is an automated, AI-driven educational platform designed to turn raw educational documents (PDFs, text passages, curricula) into structured, high-quality assessment datasets.

### Core Capabilities:
1. **Document Ingestion & Chunking**: Streams PDF/TXT documents asynchronously and chunks them for LLM processing.
2. **Automated Learning Outcome (LO) Extraction**: Uses Google Gemini to analyze context and extract explicit, verifiable Learning Outcomes (`text`, `concept`, `source_evidence`).
3. **Multi-Type Question Generation**: Generates Multiple-Choice Questions (MCQs), True/False, and Short Answer questions aligned with specific LOs and difficulty distributions.
4. **Semantic Question-to-LO Linking**: Uses local embedding similarity (`sentence-transformers`) to score question-to-outcome alignment with confidence scores and reasoning.
5. **8-Criteria LLM-as-Judge Evaluation**: Scores generated questions across 8 strict criteria (grounding, clarity, answer correctness, explanation correctness, LO alignment, difficulty, validity, choices) and categorizes items as `accepted`, `needs_review`, or `rejected`.
6. **Clean Dataset Export**: Filters approved assessment data for downstream usage.
7. **Training Pair Construction & Fine-Tuning**: Generates positive, negative, and Jaccard-based hard-negative pairs to fine-tune embedding models using `CosineSimilarityLoss`.
8. **Vector Similarity Recommendation**: Uses ChromaDB and Gemini embeddings to perform semantic search and recommend relevant questions for user queries.

---

## 🏗️ 2. Architectural Breakdown & Team Roles

The system is organized into three decoupled, complementary layers:

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │                 FastAPI REST API Layer                 │
                                    └───────────────────────────┬────────────────────────────┘
                                                                │
                      ┌─────────────────────────────────────────┴─────────────────────────────────────────┐
                      ▼                                                                                   ▼
┌───────────────────────────────────────────┐                               ┌───────────────────────────────────────────┐
│     P1: API, Data & Export Layer          │                               │      P2: AI & LangGraph Pipeline           │
│  - FastAPI Routes & Request Schemas       │                               │  - 5-Node State Machine Pipeline          │
│  - Document Ingestion & Async Chunking    │                               │  - Google Gemini Structured Output        │
│  - PostgreSQL Async Engine & Alembic      │                               │  - SBERT Question-to-LO Linker            │
│  - CRUD Layer & Dataset Export Endpoint   │                               │  - 8-Criteria LLM-as-Judge Evaluator      │
└─────────────────────┬─────────────────────┘                               └─────────────────────┬─────────────────────┘
                      │                                                                           │
                      └─────────────────────────────────────────┬─────────────────────────────────┘
                                                                ▼
                                    ┌────────────────────────────────────────────────────────┐
                                    │        P3: Infrastructure, Vector DB & ML Tuning       │
                                    │  - Docker Compose (Postgres, Redis, ChromaDB)          │
                                    │  - Redis Caching Layer (Idempotency & Embeddings)      │
                                    │  - VectorStoreService (ChromaDB + text-embedding-004)  │
                                    │  - Pair Generator & SentenceTransformerTrainer         │
                                    └────────────────────────────────────────────────────────┘
```

| Layer | Primary Responsibilities | Key Files / Modules |
|---|---|---|
| **P1: API & Data** | Endpoints (`/health`, `/data/*`, `/dataset/export`), File Ingestion, PostgreSQL ORM, Async CRUD Operations | `routes/data.py`, `routes/dataset.py`, `controllers/`, `models/`, `helpers/db.py` |
| **P2: AI Pipeline** | LangGraph Orchestration, Gemini API Wrapper, LO Extraction, Question Generation, Semantic Linker, LLM-as-Judge Evaluator | `graph/graph.py`, `services/gemini_client.py`, `services/lo_extraction.py`, `services/question_generator.py`, `services/lo_linker.py`, `services/evaluator.py` |
| **P3: Infra & ML** | Docker Stack, Redis Cache, ChromaDB Vector DB, Training Pair Generator, Embedding Model Fine-Tuning | `docker/docker-compose.yml`, `helpers/redis_client.py`, `helpers/hashing.py`, `services/embedding_service.py`, `stores/vector/vector_store.py`, `services/pair_generator.py`, `training/fine_tune.py` |

---

## 🔄 3. System Flow & Data Lifecycle

### 🌊 1. Ingestion & Processing Flow (`/api/v1/data/*`)
1. User uploads a PDF or TXT file to `POST /data/upload/{project_id}`.
2. `DataController` validates format and file size limit, generates a unique filename, and writes chunks asynchronously using `aiofiles`.
3. User triggers `POST /data/process/{project_id}`. `ProcessController` offloads heavy PyMuPDF/TXT parsing to a threadpool (`asyncio.to_thread`) to prevent blocking the event loop, splitting text into structured chunks (`RecursiveCharacterTextSplitter`).

### ⚡ 2. Generation & Evaluation Flow (`POST /api/v1/dataset/generate`)
```mermaid
flowchart TD
    A[EducationalContext Payload] --> B[Compute Context Hash: sha256 passage + config]
    B --> C{Check Redis Cache}
    C -->|Cache Hit| D[Return Cached JSON Instantly - 2ms]
    C -->|Cache Miss| E[LangGraph 5-Node State Machine]
    
    E --> E1[Node 1: parse_node]
    E1 --> E2[Node 2: extract_outcomes_node via Gemini]
    E2 --> E3[Node 3: generate_questions_node via Gemini]
    E3 --> E4[Node 4: link_outcomes_node via SBERT]
    E4 --> E5[Node 5: evaluate_node via LLM-as-Judge]
    
    E5 --> F{Evaluate Batch Status}
    F -->|All Rejected| G[log_and_discard_node: Log & Skip DB Write]
    F -->|Accepted / Needs Review| H[store_node: Save LOs, Questions, Links, Evals to PostgreSQL]
    
    H --> I[Store Result JSON in Redis - TTL 24h]
    I --> J[Return Response Summary JSON]
```

### 🎯 3. Recommendation & Training Flow
1. **Export (`GET /dataset/export`)**: Queries PostgreSQL for questions with status `accepted` or `needs_review`, matches them with their LOs and evaluation scores, and exports clean JSON arrays.
2. **Pair Building (`POST /training-pairs/build`)**: Converts DB records into `QuestionWithLO` objects, executes `generate_pairs()` to produce positive, negative, and hard-negative pairs, and writes `assets/training_pairs.jsonl`.
3. **Fine-Tuning (`training/fine_tune.py`)**: Trains `SentenceTransformer` (`paraphrase-multilingual-mpnet-base-v2`) on pairs using `CosineSimilarityLoss`.
4. **Semantic Search (`POST /recommendations/questions`)**: Converts user search query to a 768-dim embedding (`text-embedding-004`), queries ChromaDB, and returns top $K$ matching questions.

---

## 🔌 4. Complete API Surface & Endpoint Reference

| Method | Path | Summary | Inputs | Output |
|---|---|---|---|---|
| `GET` | `/api/v1/health` | Service health status | None | `{"status": "ok", "version": "0.1", "app": "smart-educator"}` |
| `POST` | `/api/v1/data/upload/{project_id}` | Upload passage file | `file: UploadFile` | `{"signal": "...", "file_id": "..."}` |
| `POST` | `/api/v1/data/process/{project_id}` | Chunk uploaded file | `ProcessRequest(file_id, chunk_size, overlap_size)` | Array of text chunk objects |
| `POST` | `/api/v1/dataset/generate` | Run full AI pipeline | `EducationalContext` JSON payload | Summary counts (`learning_outcomes_created`, `questions_created`, etc.) |
| `POST` | `/api/v1/dataset/evaluate` | Re-evaluate DB questions | `EvaluateRequest(question_ids: Optional[list])` | `{"questions_evaluated": N, "status_breakdown": {...}}` |
| `GET` | `/api/v1/dataset/export` | Export clean dataset | Query param: `difficulty` (optional) | Array of PRD §8.6 flat dataset records |
| `POST` | `/api/v1/training-pairs/build` | Generate training pairs | None | `{"total_pairs": N, "positive_pairs": X, "negative_pairs": Y, "hard_negative_pairs": Z}` |
| `POST` | `/api/v1/recommendations/questions` | Vector similarity search | `RecommendationRequest(query, top_k, difficulty)` | `{"query": "...", "recommendations": [...]}` |

---

## 🗄️ 5. Database Schemas & Persistence Layer

PostgreSQL schema auto-creates on FastAPI startup via `create_tables()` in `main.py`.

```
                    ┌─────────────────────────┐
                    │    learning_outcomes    │
                    ├─────────────────────────┤
                    │ id (UUID, PK)           │
                    │ text (String)           │
                    │ concept (String)        │
                    │ source_evidence (String)│
                    │ context_hash (Indexed)  │
                    └────────────▲────────────┘
                                 │
                                 │ (via QuestionLOLink)
                                 │
                    ┌────────────┴────────────┐
                    │    question_lo_links    │
                    ├─────────────────────────┤
                    │ id (UUID, PK)           │
                    │ question_id (FK) ───────┼──────────┐
                    │ lo_id (FK)              │          │
                    │ confidence (Float)      │          │
                    │ reason (String)         │          │
                    └─────────────────────────┘          │
                                                         │
                                                         ▼
┌─────────────────────────┐                 ┌─────────────────────────┐
│   evaluation_results    │                 │        questions        │
├─────────────────────────┤                 ├─────────────────────────┤
│ id (UUID, PK)           │                 │ id (UUID, PK)           │
│ question_id (FK) ───────┼─────────────────┤ question_text (String)  │
│ 8 Criteria Scores (0-1) │                 │ question_type (String)  │
│ overall_score (Float)   │                 │ choices (JSON)          │
│ status (Enum String)    │                 │ correct_answer (String) │
└─────────────────────────┘                 │ explanation (String)    │
                                            │ difficulty (String)     │
                                            │ estimated_time_minutes  │
                                            │ related_LO_ids (JSON)   │
                                            │ source_evidence (String)│
                                            └─────────────────────────┘
```

---

## ⚡ 6. Caching & Vector DB Infrastructure

### 🔴 Redis Caching Layer ([redis_client.py](file:///home/moabed/Documents/Smart-Educator/src/helpers/redis_client.py))
- **Pipeline Cache (`dataset_generate:<sha256_hash>`)**: Caches complete `/dataset/generate` output payloads for 24 hours (`REDIS_TTL=86400`).
- **Embedding Cache (`embedding:<sha256_text_model>`)**: Caches 768-dim Google `text-embedding-004` vectors to minimize API usage.

### 🔷 ChromaDB Vector DB ([vector_store.py](file:///home/moabed/Documents/Smart-Educator/src/stores/vector/vector_store.py))
- Stores question text vectors in collection `"questions"`.
- Performs $L_2$ / Cosine distance nearest-neighbor search (`search(query_embedding, top_k)`).

---

## 📂 7. Codebase Walkthrough by Component

```
src/
├── main.py                          ← App entry point, lifecycle startup, router registration
├── .env                             ← Local settings (DB URL, Gemini API Key, Redis, Chroma)
│
├── helpers/
│   ├── config.py                    ← BaseSettings schema with LRU cache & fallbacks
│   ├── db.py                        ← Async SQLAlchemy engine, Base, and get_db session dependency
│   ├── redis_client.py               ← Async Redis client with get_cached() and set_cached()
│   └── hashing.py                    ← SHA256 context hasher
│
├── models/                          ← SQLAlchemy ORM Table Definitions
│   ├── learningOutcome.py
│   ├── questions.py
│   ├── questionL0Link.py
│   └── evaluationResult.py
│
├── routes/                          ← API Routers
│   ├── base.py                      ← GET /health
│   ├── data.py                      ← POST /upload, POST /process
│   ├── dataset.py                   ← POST /generate, POST /evaluate, GET /export
│   ├── training_pairs.py            ← POST /build
│   └── recommendations_questions.py ← POST /questions
│
├── controllers/
│   ├── CRUD_Operations/             ← Async DB Operations
│   │   ├── learning_outcomes.py
│   │   ├── questions.py
│   │   ├── question_lo_links.py
│   │   └── evaluation_results.py
│   ├── DataController.py            ← Upload validation and unique filename generation
│   ├── ProcessController.py         ← Async PDF/TXT loader and character text chunking
│   └── ProjectController.py         ← File path management
│
├── services/                        ← Core AI & ML Services
│   ├── gemini_client.py              ← Gemini SDK wrapper with retries & structured output
│   ├── lo_extraction.py              ← Extract LOs using Gemini
│   ├── question_generator.py         ← Generate MCQs/TF/Short Answer using Gemini
│   ├── lo_linker.py                  ← Local SBERT semantic similarity linker
│   ├── evaluator.py                  ← 8-criteria LLM-as-Judge evaluator
│   ├── pair_generator.py             ← Positive / Negative / Hard-Negative pair builder
│   └── embedding_service.py          ← Text embedding service (Redis-cached)
│
├── graph/
│   └── graph.py                      ← LangGraph 5-node orchestration pipeline
│
├── stores/vector/
│   └── vector_store.py               ← VectorStoreService wrapping ChromaDB HttpClient
│
└── training/
    └── fine_tune.py                  ← SentenceTransformerTrainer fine-tuning logic
```

---

## 💻 8. Step-by-Step Setup & How-to-Run Guide

### Step 1: Environment Configuration
Copy `.env.example` to `.env` in `src/.env` and verify settings:
```env
APP_NAME="smart-educator"
APP_VERSION="0.1"
GEMINI_API_KEY="your_actual_gemini_api_key"

DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/smart_educator"

REDIS_HOST="localhost"
REDIS_PORT=6379
CHROMA_HOST="localhost"
CHROMA_PORT=8000
REDIS_TTL=86400
```

### Step 2: Spin Up Infrastructure Containers
```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps
```

### Step 3: Install Dependencies
```bash
pip install -r src/requirements.txt
```

### Step 4: Run the Server
> ⚠️ **IMPORTANT:** Always run commands from the **project root directory** (so relative `.env` resolution works).

```bash
python -m uvicorn main:app --app-dir src --reload --port 8000
```

- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🔍 9. Troubleshooting & Maintenance Checklist

| Symptom / Error | Root Cause | Solution |
|---|---|---|
| `ValidationError: Field required` on startup | Executing python commands from inside `src/` directory | Execute commands from the project root: `python -m uvicorn main:app --app-dir src` |
| `Redis connection error` / `ConnectionRefusedError` | Docker Redis container is offline | Run `docker compose -f docker/docker-compose.yml up -d` |
| `Cannot connect to Postgres on port 5432` | Local PostgreSQL instance conflict or container down | Ensure container is healthy via `docker compose ps` |
| Fast API Event Loop freezes during PDF upload | Synchronous file loader called directly | Wrap loader calls using `await asyncio.to_thread(loader.load)` |
| `google-generativeai` import errors | Deprecated Gemini SDK | Use `from google import genai` (`google-genai` package) |

---

> **Document Status:** Master Architecture Report Complete & Verified (`v0.1.0`).
