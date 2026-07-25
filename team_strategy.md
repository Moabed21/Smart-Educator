# Smart-Educator — 3-Person Team Strategy

> Based on actual project state: 2026-07-17
> Sprint deadline: 2026-08-01 (15 calendar days remaining)

---

## What's Actually Done Today

| Item | Status |
|---|---|
| FastAPI skeleton + 2 routes (upload, process) | ✅ Done |
| BaseController / DataController / ProjectController / ProcessController | ✅ Done |
| Pydantic BaseSettings + `.env.example` | ✅ Done |
| `requirements.txt` (full sprint) | ✅ Done |
| `docker-compose.yml` | ❌ Empty file |
| Alembic / PostgreSQL models | ❌ Not started |
| PRD Pydantic schemas (5 schemas) | ❌ Not started |
| Gemini integration | ❌ Not started |
| LangGraph pipeline | ❌ Not started |
| Redis caching | ❌ Not started |
| ChromaDB | ❌ Not started |
| All Sprint 2 features | ❌ Not started |

**Remaining work: ~23–24 person-days across 15 calendar days.**
With 3 people working well in parallel: **achievable if started immediately with clear ownership.**

---

## Core Principle: Learn-While-Build

> Don't study a tool completely before touching the project.
> Study the minimum needed for your current task, build it, then move to the next concept.

Each person below has a "study first" box and a "then build" box for every phase. The study time is budgeted **inside** the task time, not separately.

---

## Team Roles

| Person | Title | Domain |
|---|---|---|
| **P1** | API & Data Engineer | FastAPI routes, Pydantic schemas, PostgreSQL models, Alembic, CRUD operations, testing |
| **P2** | AI / LLM Engineer | Gemini API, LO extraction, question generation, LLM-as-Judge evaluation, LangGraph nodes |
| **P3** | Infrastructure & ML Engineer | Docker Compose, Redis, ChromaDB, embeddings, sentence-transformers fine-tuning |

---

## What Each Person Builds — Full Breakdown

---

### 👤 P1 — API & Data Engineer

#### Phase 1: Foundation (Days 1–2)

**Study first (2 hours):**
- FastAPI `Depends()` pattern — [fastapi.tiangolo.com/tutorial/dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- SQLAlchemy 2.0 async session — [docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

**Then build:**

1. **All 5 PRD Pydantic Schemas** in `src/routes/schemes/` or `src/schemas/`:
   - `EducationalContext` — has `question_config` + `difficulty_distribution`
   - `LearningOutcome` — `id`, `text`, `concept`, `source_evidence`
   - `Question` — full: choices, explanation, difficulty, `estimated_time_minutes`, `related_LO_ids`
   - `EvaluationResult` — 8 score fields + `status: accepted/rejected/needs_review`
   - `QuestionLOLink` — `confidence`, `reason`

2. **`GET /health` endpoint** in `src/routes/base.py`:
   ```python
   @base_router.get("/health")
   async def health(settings: Settings = Depends(get_settings)):
       return {"status": "ok", "version": settings.APP_VERSION, "app": settings.APP_NAME}
   ```

3. **Register 4 stub endpoints** (return 501) in a new `src/routes/dataset.py`:
   - `POST /dataset/generate`
   - `POST /dataset/evaluate`
   - `GET /dataset/export`
   - `POST /training-pairs/build`
   - `POST /recommendations/questions`

4. **PostgreSQL ORM models** in `src/models/`:
   - `LearningOutcome` table
   - `Question` table
   - `QuestionLOLink` table
   - `EvaluationResult` table

5. **Async DB session dependency** in `src/helpers/db.py`:
   ```python
   async def get_db() -> AsyncSession:
       async with AsyncSession(engine) as session:
           yield session
   ```

---

#### Phase 2: CRUD & Persistence (Days 3–5)

**Study first (1 hour):**
- Alembic autogenerate — [alembic.sqlalchemy.org/en/latest/autogenerate.html](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)

**Then build:**

1. **Alembic init + first migration** for `learning_outcomes` table
2. **CRUD module** `src/stores/sql/` with:
   - `save_learning_outcomes(session, outcomes: list[LearningOutcome])`
   - `get_outcomes_by_context_hash(session, hash: str)`
   - `save_questions(session, questions: list[Question])`
   - `save_question_lo_links(session, links: list[QuestionLOLink])`
   - `save_evaluation_results(session, evals: list[EvaluationResult])`
3. **Migration for questions + links + evals tables**
4. Wire CRUD calls into the route endpoints once P2 has the AI output ready

---

#### Phase 3: Export + Tests (Days 8–10)

**Then build:**
1. **`GET /dataset/export`** — query only `accepted` + `needs_review`, serialize to flat JSON
2. **`POST /training-pairs/build`** — trigger DB query, persist pair records
3. **Full pytest suite** (`tests/` dir):
   - Schema validation tests
   - Route integration tests using `httpx.AsyncClient`
   - DB state assertions

---

### 👤 P2 — AI / LLM Engineer

#### Phase 1: Gemini Client (Days 1–2)

**Study first (3 hours):**
- Gemini structured output (function calling) — [ai.google.dev/gemini-api/docs/function-calling](https://ai.google.dev/gemini-api/docs/function-calling)
- LangGraph quickstart — [langchain-ai.github.io/langgraph/tutorials/introduction](https://langchain-ai.github.io/langgraph/tutorials/introduction/)

**Then build:**

1. **`src/services/gemini_client.py`** — wrapper with:
   - `generate_structured_output(prompt, response_schema)` — uses Gemini function calling
   - Exponential backoff retry (max 3 attempts, 2s → 4s → 8s)
   - Quota error handling

2. **`src/services/lo_extraction.py`** — Learning Outcome extraction:
   - Takes `EducationalContext` as input
   - Builds prompt with the passage text
   - Calls `gemini_client.generate_structured_output()` with `LearningOutcome` schema
   - Returns `list[LearningOutcome]` with generated IDs (`LO_001`, `LO_002` ...)

---

#### Phase 2: Question Generation + Linking (Days 3–5)

**Study first (1 hour):**
- LangGraph `TypedDict` state and conditional edges — [langchain-ai.github.io/langgraph/how-tos/branching](https://langchain-ai.github.io/langgraph/how-tos/branching/)

**Then build:**

1. **`src/services/question_generator.py`**:
   - Takes LOs + `question_config` from the context
   - Prompt respects: MCQ (4 choices), True/False, Short Answer
   - Respects `difficulty_distribution` from input
   - Returns `list[Question]`

2. **`src/services/lo_linker.py`**:
   - For each question → assign best matching `LearningOutcome`
   - Compute `confidence` score (use semantic similarity via embedding dot product as fallback)
   - Returns `list[QuestionLOLink]`

3. **`src/graph/graph.py`** — LangGraph pipeline:
   ```python
   class GraphState(TypedDict):
       context: EducationalContext
       context_hash: str
       learning_outcomes: list[LearningOutcome]
       questions: list[Question]
       lo_links: list[QuestionLOLink]
       evaluations: list[EvaluationResult]

   # Nodes:
   # parse_node → extract_outcomes_node → generate_questions_node
   # → link_outcomes_node → evaluate_node
   ```

4. **Conditional edge** after `evaluate_node`:
   - `accepted` or `needs_review` → `store_node` (calls P1's CRUD)
   - `rejected` → `log_and_discard_node`

---

#### Phase 3: LLM-as-Judge Evaluator (Days 5–7)

**Then build:**

1. **`src/services/evaluator.py`** — 8-criteria scorer:
   - `context_grounding_score` — does question come from the passage?
   - `clarity_score` — is the question clear?
   - `answer_correctness_score` — is the answer correct?
   - `explanation_correctness_score` — is the explanation valid?
   - `learning_outcome_alignment_score` — does it test the right LO?
   - `difficulty_score` — matches requested difficulty?
   - `question_type_validity_score` — is format correct?
   - `choices_validity_score` — (MCQ only) are distractors plausible?
   - Compute `overall_score` = weighted average
   - Set `status`: `accepted` (≥0.75), `needs_review` (0.5–0.74), `rejected` (<0.5)

2. Wire evaluator into LangGraph `evaluate_node`

3. Wire the full graph into `POST /dataset/generate` and `POST /dataset/evaluate` endpoints

---

#### Phase 4: Recommendation Logic (Days 10–12)

**Then build:**

1. **`src/services/recommender.py`**:
   - Accept `{"query": "...", "top_k": 5}`
   - Embed query using current model (base or fine-tuned)
   - Call `VectorStoreService.search()` (from P3)
   - Return top-K with scores

2. **Before/after evaluation**:
   - Run same queries on base model vs fine-tuned model
   - Compute Top-K LO match rate for each
   - Log delta and export comparison JSON

---

### 👤 P3 — Infrastructure & ML Engineer

#### Phase 1: Docker + Services (Days 1–2)

**Study first (1 hour):**
- Docker Compose services with health checks — [docs.docker.com/compose/compose-file](https://docs.docker.com/compose/compose-file/)
- ChromaDB Python client — [docs.trychroma.com/getting-started](https://docs.trychroma.com/getting-started)

**Then build:**

1. **`docker/docker-compose.yml`** with:
   - `postgres:16` — port 5432, volume, health check
   - `chromadb/chroma` — port 8000, volume
   - `redis:7` — port 6379, volume

2. **`src/helpers/redis_client.py`** — async Redis wrapper:
   ```python
   async def get_cached(key: str) -> str | None
   async def set_cached(key: str, value: str, ttl_seconds: int = 3600)
   ```

3. **Cache integration** in `POST /dataset/generate`:
   - Cache key = `sha256(json(educational_context) + json(question_config))`
   - Return cached result if hit, skip entire LangGraph pipeline

---

#### Phase 2: Vector Store (Days 3–5)

**Study first (2 hours):**
- ChromaDB collections, upsert, query — [docs.trychroma.com/usage-guide](https://docs.trychroma.com/usage-guide)
- `text-embedding-004` via `google-generativeai` — [ai.google.dev/gemini-api/docs/embeddings](https://ai.google.dev/gemini-api/docs/embeddings)

**Then build:**

1. **`src/stores/vector/vector_store.py`** — `VectorStoreService`:
   ```python
   class VectorStoreService:
       def upsert_questions(self, questions: list[Question], embeddings: list[list[float]])
       def search(self, query_embedding: list[float], top_k: int, filters: dict) -> list[dict]
   ```

2. **`src/services/embedding_service.py`**:
   - `embed_text(text: str) -> list[float]` — calls `text-embedding-004`
   - `embed_batch(texts: list[str]) -> list[list[float]]` — batched for efficiency
   - Redis cache: key = `sha256(text + model_version)`

3. **Embed all accepted questions** after Sprint 1 pipeline is ready, upsert into ChromaDB with metadata (`question_id`, `difficulty`, `lo_ids`, `subject`)

---

#### Phase 3: Fine-Tuning (Days 8–12)

**Study first (2 hours):**
- `sentence-transformers` training overview — [sbert.net/docs/training/overview.html](https://www.sbert.net/docs/training/overview.html)
- `MultipleNegativesRankingLoss` — [sbert.net/docs/package_reference/losses.html](https://www.sbert.net/docs/package_reference/losses.html)

**Then build:**

1. **`src/training/fine_tune.py`** — standalone script:
   - Load training pairs from DB (positive, negative, hard-negative)
   - Load base model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (multilingual, no GPU needed)
   - Train with `MultipleNegativesRankingLoss`
   - Save model to `src/assets/models/fine_tuned_v1/`

2. **Hot-swap after fine-tuning**:
   - Re-embed all accepted questions with fine-tuned model
   - Update ChromaDB collection with new vectors
   - Add `embedding_model_version` column to questions table
   - Update `embedding_service.py` to load fine-tuned model by default

3. **`src/services/pair_generator.py`**:
   - Positive pairs: questions sharing same LO + concept, not identical
   - Negative pairs: questions from different LOs
   - Hard-negative pairs: similar wording, different LOs (keyword overlap check)
   - Export as JSONL for fine-tuning

---

## Dependency Map — When Each Task Unlocks the Next

```
P3: Docker up (Day 1)
    └── P1: Alembic can run migrations (Day 2)
        └── P2: LangGraph can persist LOs to DB (Day 3-4)

P1: PRD Schemas done (Day 1)
    └── P2: Can write Gemini prompts against real schema (Day 2)
    └── P3: Can structure ChromaDB metadata correctly (Day 3)

P2: LO extraction working (Day 3)
    └── P2: Question generation starts (Day 4)
        └── P2: LO linking + evaluation (Day 5-6)
            └── P1: Wire final endpoints (Day 7)
                └── P3: Embeddings + ChromaDB upsert (Day 8)
                    └── P2+P3: Fine-tune + hot-swap (Day 9-11)
                        └── P2: Before/after evaluation (Day 12)
```

---

## Week-by-Week Calendar (3 people, 15 days left)

### Week 3 (Jul 18–22) — Foundation + Core AI Pipeline

| Day | P1 (API/DB) | P2 (AI/LLM) | P3 (Infra/ML) |
|---|---|---|---|
| **Jul 18** | PRD schemas (all 5) + GET /health + stub endpoints | Read Gemini structured output docs + build gemini_client.py | docker-compose.yml (PG + Chroma + Redis) + test it |
| **Jul 19** | PostgreSQL ORM models (4 tables) | LO extraction service (prompt + structured output) | redis_client.py + cache integration in route |
| **Jul 20** | Alembic init + all migrations | LO extraction tested on real passage | embedding_service.py (text-embedding-004 + batch) |
| **Jul 21** | CRUD: save/get LOs, questions, links, evals | Question generation service (MCQ/TF/SA) | VectorStoreService (upsert + search) |
| **Jul 22** | Wire DB session into routes + integration test | LO linking + confidence scoring | Embed accepted questions → ChromaDB upsert |

### Week 4 (Jul 23–29) — Evaluation + Intelligence Layer + Release

| Day | P1 (API/DB) | P2 (AI/LLM) | P3 (Infra/ML) |
|---|---|---|---|
| **Jul 23** | GET /dataset/export endpoint | LLM-as-Judge evaluator (8 criteria) | pair_generator.py (positive/negative/hard-neg) |
| **Jul 24** | POST /training-pairs/build endpoint | LangGraph full 5-node pipeline | Fine-tuning script (sentence-transformers) |
| **Jul 25** | Wire POST /dataset/generate + evaluate | POST /recommendations/questions route | Run fine-tuning + save model artifact |
| **Jul 26** | Full pytest E2E test suite | Before/after recommendation evaluation | Hot-swap: re-embed with fine-tuned model |
| **Jul 27** | Hardening: rate limiting, input size limits | Hardening: retry logic, circuit breaker | Load test + seed DB (Science Grade 5 example) |
| **Jul 28** | Fix test failures + code review | Evaluation report (before-vs-after JSON) | Structured JSON logging + request_id |
| **Jul 29** | README + .env.example + Swagger check | Final demo dry run | Docker Compose final + tag v0.1.0 |

---

## Communication Rules (Critical for Parallel Work)

1. **Schema is the contract** — P1 finalizes all 5 PRD schemas on Day 1. P2 and P3 don't start their services until schemas are shared. This prevents integration headaches.

2. **Interface-first for shared services** — P3 defines `VectorStoreService.upsert()` and `VectorStoreService.search()` signatures on Day 3, even if implementation isn't done. P2 can write against the interface immediately.

3. **No shared state in controllers** — each service is stateless and takes explicit arguments. Makes parallel work merge-safe.

4. **Git branches**: `p1/db-models`, `p2/ai-pipeline`, `p3/infra` — merge to `main` at end of each day after confirming no conflicts.

5. **Blocker call rule**: If anyone is blocked for more than 2 hours, sync immediately. Don't wait for end-of-day.

---

## The 3 Biggest Risks

| Risk | Mitigation |
|---|---|
| **Gemini prompt quality** (P2) — structured output may not parse correctly | Test LO extraction with 3 different real passages on Day 2 before building on top of it |
| **Docker connectivity** (P3) — Alembic can't run if Postgres isn't reachable | P3 must have `docker compose up` healthy by end of Day 1, tested with `pg_isready` |
| **Schema mismatch** (P1 vs P2) — if Question schema changes after P2 built the prompt | Freeze schemas after Day 1. Any change must be discussed with both P2 and P3 |
