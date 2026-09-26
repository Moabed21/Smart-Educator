# 🧠 Smart-Educator: Unified Architecture & System Master Blueprint

> **The definitive technical guide, architecture blueprint, and mental model for Smart-Educator.**  
> Keep this document as your single source of truth for how the system is designed, how data flows through it, and how to run or extend it.

---

## 1. 🎯 Project Identity & Core Mission

**Smart-Educator** is an automated, AI-driven educational assessment and adaptive learning engine. It transforms raw educational materials (passages, lessons, textbooks, PDFs) into verified, pedagogically sound assessment banks, and provides an adaptive testing loop that personalizes learning based on student weaknesses.

### Core Capabilities
1. **Atomic Learning Outcome (LO) Extraction:** Extracts distinct, verifiable learning outcomes with cited textual evidence.
2. **Multi-Format Question Generation:** Produces balanced sets of MCQs, True/False, and Short-Answer questions according to customized Bloom's difficulty distributions.
3. **High-Dimensional Semantic Linking:** Matches generated questions back to their target learning outcomes using 3072-dimensional vector embeddings and cosine similarity.
4. **Pedagogical LLM-as-Judge:** Evaluates every question across 8 rigorous quality criteria (grounding, clarity, correctness, alignment, distractor plausibility) and classifies them as `ACCEPTED`, `NEEDS_REVIEW`, or `REJECTED`.
5. **Dual Persistence & Instant Caching:** Relational storage in PostgreSQL (with Alembic migrations), vector indexing in ChromaDB, and SHA-256 context caching in Redis (2ms cached responses).
6. **Adaptive Student Testing & Diagnostic Recommendations:** Interactive student quiz interface that pinpoints weak concepts and queries ChromaDB to recommend targeted practice questions.
7. **Contrastive Fine-Tuning Pipeline:** Generates positive, negative, and Jaccard-filtered hard-negative training pairs for embedding model fine-tuning.

---

## 2. 🛠️ Technology Stack & Rationale

| Category | Technology | Purpose & Rationale |
| :--- | :--- | :--- |
| **API & Framework** | **FastAPI + Uvicorn** | High-performance asynchronous REST API, OpenAPI docs, and native Pydantic validation. |
| **Orchestration** | **LangGraph** | Deterministic state machine managing the 5-node AI generation and evaluation pipeline. |
| **LLM Engine** | **Google Gemini 2.5 / Flash** | State-of-the-art multimodal extraction, reasoning, structured JSON generation, and judgment. |
| **Vector Embeddings** | **Gemini Embeddings API (3072d)** | High-dimensional semantic vectors for Arabic and English educational taxonomies. |
| **Relational Database** | **PostgreSQL 16 + SQLAlchemy Async** | Persistent relational storage with async connection pooling (`pool_size=10`) and foreign key cascades. |
| **Database Migrations**| **Alembic (Async)** | Version-controlled, reproducible schema migrations across staging and production. |
| **Vector Database** | **ChromaDB** | Vector similarity search engine for semantic question retrieval and adaptive recommendations. |
| **Caching Layer** | **Redis 7** | 24-hour TTL caching of pipeline outputs based on SHA-256 context fingerprints. |
| **Document Processing**| **PyMuPDF (fitz)** | Lightweight, zero-dependency PDF text and page extraction. |
| **Automated Testing** | **Pytest + Pytest-Asyncio + HTTPX**| 28 automated tests running in <0.3s with `NullPool` event-loop isolation. |
| **Containerization** | **Docker & Docker Compose** | Multi-service orchestration (`api`, `postgres`, `redis`, `chromadb`) in a ~190MB lean container. |
| **Web Interface** | **HTML5 + Vanilla CSS + JS** | Dark glassmorphic Web Studio UI with real-time pipeline tracker and quiz grading. |

---

## 3. 🔄 End-to-End System & Data Flow

```
[ Raw Educational Document / Passage ]
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 1. INGESTION & SEMANTIC CHUNKING (file_service.py)     │
│    - Extracts text via PyMuPDF (PDF) or UTF-8 reader   │
│    - Splits large multi-lesson texts with 200-char     │
│      overlap to preserve cross-boundary context        │
└──────────────────────┬─────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 2. CONTEXT HASHING & REDIS DEDUPLICATION (hashing.py)  │
│    - Computes SHA-256 hash of subject + grade + passage│
│    - Cache Hit: Returns cached result in 0.002s        │
│    - Cache Miss: Triggers LangGraph Pipeline           │
└──────────────────────┬─────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ 3. LANGGRAPH 5-STAGE AI PIPELINE (graph.py)            │
│                                                        │
│  [Stage 1: LO Extraction] (lo_extraction.py)           │
│    └─► Gemini extracts atomic LOs + source_evidence    │
│                                                        │
│  [Stage 2: Question Generation] (question_generator.py)│
│    └─► Gemini generates MCQs, T/F, Short-Answer        │
│                                                        │
│  [Stage 3: High-Dim Semantic Linking] (lo_linker.py)   │
│    └─► 3072d Gemini Embeddings + Cosine Similarity     │
│                                                        │
│  [Stage 4: LLM-as-Judge Evaluation] (evaluator.py)     │
│    └─► 8 Criteria Scoring -> ACCEPTED / NEEDS_REVIEW   │
│                                                        │
│  [Stage 5: Dual Persistence & Auto-Index] (store_node) │
│    ├─► PostgreSQL: Saves LOs, Questions, Links, Evals  │
│    └─► ChromaDB: Auto-indexes question embeddings      │
└──────────────────────┬─────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌──────────────────────┐ ┌────────────────────────────────┐
│ 4. VECTOR SEARCH     │ │ 5. ADAPTIVE QUIZ & DIAGNOSIS   │
│    (ChromaDB)        │ │    (index.html)                │
│ - Semantic search by │ │ - Interactive student exam     │
│   concept or keyword │ │ - Automatic grading & report   │
│ - Top-K nearest Qs   │ │ - Identifies failed LOs        │
│ - Cosine similarity  │ │ - Recommends targeted practice │
└──────────────────────┘ └────────────────────────────────┘
```

---

## 4. 🗂️ Clean Directory Structure & Sitemap

```
Smart-Educator/
├── assets/                    # Shared assets (sample multi-lesson texts, exported files)
│   ├── multi_lesson_sample.txt
│   └── training_pairs.jsonl
├── docker/                    # Container orchestration
│   ├── Dockerfile             # Single-stage fast production Docker image
│   └── docker-compose.yml     # Multi-container stack (API, Postgres, Redis, ChromaDB)
├── info/                      # Documentation and blueprint specifications
│   ├── .env.example           # Template environment configuration
│   ├── PROJECT_BLUEPRINT.md   # Unified system master blueprint (this file)
│   ├── diagrams.drawio        # Architectural system diagrams (source)
│   └── diagrams.png           # Rendered architectural diagram
├── migrations/                # Alembic database migrations
│   ├── env.py                 # Async migration runner
│   └── versions/              # Migration versions (001_initial_schema.py)
├── tests/                     # Automated testing suite (29 tests)
│   ├── conftest.py            # Test engine fixtures with NullPool
│   ├── test_api_endpoints.py  # Route and probe tests
│   ├── test_evaluator.py      # 8-criteria scoring tests
│   ├── test_multi_context_pipeline.py # Chunking and context isolation tests
│   ├── test_pair_generator.py # Jaccard similarity & triplet pair tests
│   └── test_schemas.py        # Pydantic validation tests
├── src/                       # Main application source
│   ├── crud/                  # Async SQLAlchemy CRUD operations
│   │   ├── evaluation_results.py
│   │   ├── learning_outcomes.py
│   │   ├── question_lo_links.py
│   │   └── questions.py
│   ├── graph/                 # LangGraph state machine workflow
│   │   └── graph.py
│   ├── helpers/               # Core infrastructure utilities
│   │   ├── config.py          # Pydantic BaseSettings & env parsing
│   │   ├── db.py              # Async connection pool, engine & DeclarativeBase
│   │   ├── hashing.py         # SHA-256 context hashing
│   │   ├── logger.py          # Correlation ID (X-Request-ID) middleware
│   │   ├── redis_client.py    # Async Redis cache client
│   │   └── security.py        # API key verification dependency
│   ├── models/                # SQLAlchemy ORM database models
│   │   ├── enums.py
│   │   ├── evaluationResult.py
│   │   ├── learningOutcome.py
│   │   ├── questionL0Link.py
│   │   └── questions.py
│   ├── routes/                # FastAPI endpoint routers
│   │   ├── base.py            # /health, /health/live, /health/ready
│   │   ├── data.py            # /api/v1/data (upload & chunking)
│   │   ├── dataset.py         # /api/v1/dataset (generate, evaluate, export)
│   │   ├── recommendations_questions.py # /api/v1/recommendations
│   │   ├── training_pairs.py  # /api/v1/training-pairs/build
│   │   └── schemes/           # Pydantic request/response schemas
│   ├── services/              # Core business & AI logic
│   │   ├── embedding_service.py # Gemini Embeddings API + Redis vector cache
│   │   ├── evaluator.py       # LLM-as-Judge 8-criteria evaluator
│   │   ├── file_service.py    # File storage, validation & chunking
│   │   ├── fine_tune.py       # Offline embedding fine-tuning script
│   │   ├── gemini_client.py   # Gemini API client wrapper
│   │   ├── lo_extraction.py   # Learning outcome extraction
│   │   ├── lo_linker.py       # Embedding cosine similarity linker
│   │   ├── pair_generator.py  # Contrastive pair generator with Jaccard metrics
│   │   ├── question_generator.py # Question generator
│   │   └── vector_store.py    # ChromaDB vector store client
│   ├── static/                # Web Studio User Interface
│   │   └── index.html         # Interactive dashboard, generator & quiz studio
│   ├── main.py                # Application entrypoint & middleware registration
│   └── requirements.txt       # Streamlined production dependencies
├── .env                       # Local environment configuration
├── .gitignore
├── alembic.ini                # Alembic migration configuration
└── README.md                  # Developer guide & architecture overview
```

---

## 5. 🗄️ Relational Database Schema Overview

Database tables are version-controlled via **Alembic migrations** to guarantee zero data loss when modifying columns in production, maintain an audit history in Git, and prevent race conditions across worker processes on application boot.

```
 ┌──────────────────────┐         ┌────────────────────────┐
 │  learning_outcomes   │         │       questions        │
 ├──────────────────────┤         ├────────────────────────┤
 │ id (UUID, PK)        │◄──┐ ┌──►│ id (UUID, PK)          │
 │ text (TEXT)          │   │ │   │ question_text (TEXT)   │
 │ concept (VARCHAR)    │   │ │   │ question_type (VARCHAR)│
 │ source_evidence      │   │ │   │ choices (JSONB)        │
 │ created_at           │   │ │   │ correct_answer (TEXT)  │
 └──────────────────────┘   │ │   │ explanation (TEXT)     │
                            │ │   │ difficulty (VARCHAR)   │
 ┌──────────────────────┐   │ │   │ status (VARCHAR)       │
 │  question_lo_links   │   │ │   └───────────┬────────────┘
 ├──────────────────────┤   │ │               │ 1:1
 │ id (UUID, PK)        │   │ │               ▼
 │ question_id (FK) ────┼───┼─┘   ┌────────────────────────┐
 │ lo_id (FK) ──────────┼───┘     │   evaluation_results   │
 │ confidence (FLOAT)   │         ├────────────────────────┤
 │ reason (TEXT)        │         │ id (UUID, PK)          │
 └──────────────────────┘         │ question_id (FK, Unique│
                                  │ context_grounding      │
                                  │ clarity, correctness   │
                                  │ overall_score (FLOAT)  │
                                  │ status (ACCEPTED / ...)│
                                  └────────────────────────┘
```

---

## 6. 🚀 How to Run & Verify

### Option 1: Local Development
```bash
# 1. Start required backing services
docker compose -f docker/docker-compose.yml up -d postgres redis chromadb

# 2. Run database migrations to head
source .venv/bin/activate
alembic upgrade head

# 3. Start development server with live reload
uvicorn main:app --app-dir src --reload --port 8000
```
* **Web Studio UI:** Open `http://localhost:8000/`
* **OpenAPI Docs:** Open `http://localhost:8000/docs`

### Option 2: Full Docker Stack
```bash
docker compose -f docker/docker-compose.yml up --build -d
```

### Option 3: Automated Test Execution
```bash
source .venv/bin/activate
pytest -v tests/
```
*(All 28 tests pass in ~0.25s)*
