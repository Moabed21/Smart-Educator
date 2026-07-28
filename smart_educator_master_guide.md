# Smart-Educator — Unified Master Architecture & Execution Guide

> **Combined P1 (API & Data), P2 (AI & LangGraph), and P3 (Infrastructure & Fine-Tuning) Handoff Guide**  
> **Project Version:** `v0.1.0-alpha`  
> **Date:** July 2026

---

## 🚀 1. Project Overview & System Purpose

**Smart-Educator** is an automated, AI-driven educational dataset generator, evaluator, and semantic recommendation engine. It transforms raw educational passages/curricula into structured, high-quality assessment datasets (MCQs, True/False, Short Answer) mapped to extracted **Learning Outcomes (LOs)**, evaluated on **8 strict quality criteria** via an LLM-as-Judge, and fine-tuned for semantic vector recommendations.

---

## 🏗️ 2. Architectural Layers & Responsibilities

The system is split into three foundational engineering layers:

```
                  ┌────────────────────────────────────────────────────────┐
                  │                 FastAPI REST API Layer                 │
                  └───────────────────────────┬────────────────────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
┌───────────────────────────────────────┐           ┌───────────────────────────────────────┐
│     P1: Core API & Persistence        │           │     P2: AI & LangGraph Pipeline       │
│  - Endpoint Routing & Validation      │           │  - 5-Node Orchestration Graph         │
│  - PostgreSQL Async Engine & ORM      │           │  - Gemini 2.5 Structured Extraction    │
│  - CRUD Operations & Serialization    │           │  - 8-Criteria LLM-as-Judge Evaluator  │
└───────────────────┬───────────────────┘           └───────────────────┬───────────────────┘
                    │                                                   │
                    └─────────────────────────┬─────────────────────────┘
                                              ▼
                  ┌────────────────────────────────────────────────────────┐
                  │       P3: Infrastructure, Vector DB & Fine-Tuning       │
                  │  - Docker Compose Stack (Postgres, Redis, ChromaDB)    │
                  │  - Redis Caching (Context Hash & Embedding Cache)      │
                  │  - VectorStoreService (ChromaDB + Gemini Embeddings)   │
                  │  - Fine-Tuning Pipeline (SentenceTransformerTrainer)   │
                  └────────────────────────────────────────────────────────┘
```

---

## 🔄 3. Deep-Dive: Inner System Flow

### 🌊 Flow 1: Dataset Generation & Evaluation (`POST /api/v1/dataset/generate`)

```
Raw Educational Context (JSON)
           │
           ▼
[ 1. Hashing & Caching ] ──► Compute SHA256(passage + config) ──► Redis Hit? ──► Return Cached JSON
           │ (Miss)
           ▼
[ 2. LangGraph Execution ]
           │
           ├─► Node 1: parse_node ──────────► Validates payload & calculates context hash
           ├─► Node 2: extract_outcomes_node ► Calls Gemini structured output (extracts LOs + concepts)
           ├─► Node 3: generate_questions_node► Generates MCQs, T/F, Short Answer per difficulty distribution
           ├─► Node 4: link_outcomes_node ───► Maps questions to LOs with confidence & reasoning
           └─► Node 5: evaluate_node ────────► 8-criteria LLM-as-Judge (accepted / rejected / needs_review)
           │
           ▼
[ 3. DB Persistence ] ──► Store LOs, Questions, Links, and Evaluations in PostgreSQL via Async CRUD
           │
           ▼
[ 4. Cache Update ] ──► Save final result to Redis (24h TTL) & return JSON payload
```

### 🎯 Flow 2: Semantic Vector Recommendation (`POST /api/v1/recommendations/questions`)

```
User Search Query: "How does evaporation lead to cloud formation?"
           │
           ▼
[ 1. Embedding ] ──► Redis Cache Check ──(Miss)──► Gemini `text-embedding-004` (or Fine-Tuned Model)
           │
           ▼
[ 2. ChromaDB Search ] ──► Similarity Search (Cosine distance, Top-K = 5)
           │
           ▼
[ 3. Outcome Matching ] ──► Retrieve matching Question IDs, Question text, and mapped Learning Outcomes
```

### 🏋️ Flow 3: Training Pair Generation & Model Fine-Tuning (`POST /api/v1/training-pairs/build`)

```
PostgreSQL Database (Accepted & Needs-Review Questions)
           │
           ▼
[ 1. Pair Generator ] ──► Generates 3 types of training pairs:
                           ├── Positive Pair (Same LO + Same Concept)       --> Label: 1.0
                           ├── Negative Pair (Different LOs)               --> Label: 0.0
                           └── Hard-Negative (Different LO + High Overlap) --> Label: 0.0
           │
           ▼
[ 2. JSONL Export ] ──► Export pairs to `training_pairs.jsonl`
           │
           ▼
[ 3. SentenceTransformerTrainer ] ──► Fine-tunes `paraphrase-multilingual-mpnet-base-v2` 
                                       using CosineSimilarityLoss
           │
           ▼
[ 4. Hot-Swap Vector DB ] ──► Re-embed questions & update ChromaDB collection
```

---

## 🔌 4. Complete API Surface

| Method | Endpoint Path | Description | Layer Owner | Status |
|---|---|---|---|---|
| `GET` | `/api/v1/health` | Service health status | P1 | ✅ Operational |
| `POST` | `/api/v1/data/upload/{project_id}` | PDF/TXT file upload | P1 | ✅ Operational |
| `POST` | `/api/v1/data/process/{project_id}` | LangChain document chunking | P1 | ✅ Operational |
| `POST` | `/api/v1/dataset/generate` | End-to-end LO extraction + Question generation | P2 / P3 | ✅ Integrated |
| `POST` | `/api/v1/dataset/evaluate` | Standalone 8-criteria LLM-as-Judge evaluation | P2 | ✅ Integrated |
| `GET` | `/api/v1/dataset/export` | Export clean dataset (`accepted` + `needs_review`) | P1 / P2 | ✅ Integrated |
| `POST` | `/api/v1/training-pairs/build` | Build positive/negative/hard-negative pairs | P3 | ✅ Integrated |
| `POST` | `/api/v1/recommendations/questions` | Vector similarity recommendation search | P3 | ✅ Integrated |

---

## 🗄️ 5. Data Models & Vector Stores

### PostgreSQL Tables (Managed via SQLAlchemy Async + Alembic)
1. **`learning_outcomes`**: Stores `id` (UUID), `text`, `concept`, `source_evidence`, `context_hash`.
2. **`questions`**: Stores `id` (UUID), `question_text`, `question_type`, `choices` (JSON), `correct_answer`, `explanation`, `difficulty`, `estimated_time_minutes`, `related_LO_ids` (JSON), `source_evidence`.
3. **`question_lo_links`**: Junction table mapping `question_id` $\leftrightarrow$ `lo_id` with `confidence` (0.0–1.0) and `reason`.
4. **`evaluation_results`**: Stores 8 individual scores (0.0–1.0), `overall_score`, and status (`accepted`, `rejected`, `needs_review`).

### Vector Store & Cache
* **Redis**: Used for prompt idempotency caching (`dataset_generate:<hash>`, 24h TTL) and text embedding caching (`embed:<hash>`, 24h TTL).
* **ChromaDB**: Collection `"questions"` storing question text embeddings alongside metadata (`question_id`, `difficulty`, `LO_ids`).

---

## 💻 6. How to Run the Project (Step-by-Step)

### Prerequisites
* **Docker & Docker Compose** installed
* **Python 3.11+** and **Conda**
* **NVIDIA GPU (Optional but recommended for fine-tuning)**: CUDA 12.6 supported.

### Step 1: Clone & Configure Environment
```bash
git clone https://github.com/Moabed21/Smart-Educator.git
cd Smart-Educator

# Create .env from example in the project root
cp .env.example .env
```

Ensure your `.env` contains:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/smart_educator
GEMINI_API_KEY=your_actual_gemini_api_key_here
REDIS_HOST=localhost
REDIS_PORT=6379
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

### Step 2: Spin Up Infrastructure Containers
```bash
docker compose -f docker/docker-compose.yml up -d

# Verify all containers (Postgres, Redis, ChromaDB) are healthy:
docker compose -f docker/docker-compose.yml ps
```

### Step 3: Set Up Python Environment & Install Dependencies
```bash
# Create and activate conda environment
conda create -n Smart-Educator python=3.11 -y
conda activate Smart-Educator

# Install dependencies
pip install -r src/requirements.txt

# (Optional - For NVIDIA GPU acceleration during fine-tuning)
pip install torch --index-url https://download.pytorch.org/whl/cu126
```

### Step 4: Launch the FastAPI Application
> ⚠️ **CRITICAL:** Always run commands from the **project root directory** (so relative `.env` resolution works correctly).

```bash
python -m uvicorn main:app --app-dir src --reload --port 8000
```

Access Interactive Documentation at:
* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📚 7. Key Concepts & Curated Learning Resources

To master the technical stack powering Smart-Educator, explore these recommended resources:

### 1. **FastAPI & Async SQLAlchemy**
* **Key Topics:** Asynchronous dependency injection (`Depends`), Pydantic v2 schemas, `asyncpg` connection pools.
* 🔗 [FastAPI Official Async Docs](https://fastapi.tiangolo.com/async/)
* 🔗 [SQLAlchemy 2.0 Async Unified Tutorial](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

### 2. **LangGraph & Multi-Node AI Pipelines**
* **Key Topics:** StateGraph, state reducers, conditional branching, LLM node error handling.
* 🔗 [LangGraph Python Documentation](https://langchain-ai.github.io/langgraph/)
* 🔗 [LangChain Google GenAI Integration Guide](https://python.langchain.com/docs/integrations/chat/google_generativeai/)

### 3. **Google Gemini API (`google-genai` SDK)**
* **Key Topics:** Structured JSON outputs (`response_schema`), Pydantic model passing, `text-embedding-004`.
* 🔗 [Google GenAI Python SDK GitHub](https://github.com/googleapis/python-genai)
* 🔗 [Gemini Structured Outputs Guide](https://ai.google.dev/gemini-api/docs/structured-output)

### 4. **Vector Databases & Sentence Transformers Fine-Tuning**
* **Key Topics:** ChromaDB collection upserts, `CosineSimilarityLoss`, `SentenceTransformerTrainer` (v5+ API), Jaccard similarity hard-negatives.
* 🔗 [Sentence-Transformers Fine-Tuning Guide](https://sbert.net/docs/sentence_transformer/training_overview.html)
* 🔗 [ChromaDB Client Documentation](https://docs.trychroma.com/)

---

## 🔍 8. Diagnostic & Troubleshooting Checklist

| Issue / Symptom | Probable Cause | Fix |
|---|---|---|
| `Pydantic Field Required` error on startup | Executing python commands from inside `src/` instead of project root | Always execute commands from project root: `python -m uvicorn main:app --app-dir src` |
| `refusing to merge unrelated histories` | Merging branches created independently | Use `git merge <branch> --allow-unrelated-histories` |
| `Cannot connect to Postgres on 5432` | Docker container not running or port blocked | Run `docker compose -f docker/docker-compose.yml up -d` and check `pg_isready` |
| Fine-tuning running very slowly on CPU | Default `torch` in requirements is CPU-only | Reinstall GPU torch: `pip install torch --index-url https://download.pytorch.org/whl/cu126` |
| `google-generativeai` import errors | Using deprecated SDK | Use modern SDK: `from google import genai` (`google-genai` package) |
