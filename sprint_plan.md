# Smart-Educator — 2-Sprint Plan (29 Days)
> Fully aligned with the PRD after diagram corrections.
> Assumes prerequisite topics (FastAPI, LangGraph, Pydantic, Gemini API, PostgreSQL, ChromaDB, Redis, sentence-transformers, LLM-as-judge) are **studied before Day 1**.
> Sprint start: **2026-07-04** · End: **2026-08-01**

---

## 🟦 Sprint 1 — Core Pipeline (Days 1–14)

**Goal**: Complete working pipeline that takes an educational context JSON, extracts learning outcomes, generates questions with answers and explanations, links them to outcomes, and evaluates each one with 8 criteria.

**Sprint 1 endpoints delivered**: `GET /health` · `POST /dataset/generate` · `POST /dataset/evaluate`

---

### 📅 Week 1 — Foundation + Ingestion + LO Extraction (Days 1–7)

| Day | Phase | Tasks |
|---|---|---|
| **1** | Foundation | Repo structure; Docker Compose: PostgreSQL + ChromaDB + Redis; env config via Pydantic `BaseSettings`; Alembic init; project layout (routers / services / schemas / agents) |
| **2** | Schemas | All Pydantic schemas per PRD §8.1–§8.5: `EducationalContext` (with `question_config` + `difficulty_distribution`), `LearningOutcome` (id, text, concept, source_evidence), `Question` (full schema with choices, explanation, difficulty, estimated_time_minutes, related_LO_ids, source_evidence), `EvaluationResult` (8 score fields + status: accepted / rejected / needs_review), `QuestionLOLink` (confidence + reason); unit tests for all schemas |
| **3** | Foundation | FastAPI skeleton: all 6 PRD endpoints registered and returning `501 Not Implemented`; `GET /health` → returns status + version; dependency injection (DB session, Gemini client); LangGraph graph scaffolding |
| **4** | Ingestion | Input parser: validate JSON payload matching PRD §8.1 example; normalize to `EducationalContext`; Redis cache key = `sha256(context + question_config)`; return cached result if hit |
| **5** | LO Extraction | Gemini API integration for **learning outcome extraction** (PRD §8.2): structured output with `function_calling`; generate LO IDs internally (`LO_001` …); extract: text, concept, source_evidence; retry with exponential backoff |
| **6** | LO Extraction | Persist learning outcomes to PostgreSQL; Alembic migration for `learning_outcomes` table; async SQLAlchemy CRUD; bulk insert; idempotency on duplicate context hash |
| **7** | LangGraph | LangGraph pipeline: `parse_node → extract_outcomes_node`; typed `GraphState` object; node-level error handling; graph execution logging |

**Week 1 Checkpoint ✓**: Gemini extracts LOs from a real passage; outcomes stored in Postgres; Redis caching works on duplicate input.

---

### 📅 Week 2 — Question Generation + Linking + Evaluation (Days 8–14)

| Day | Phase | Tasks |
|---|---|---|
| **8** | Ingestion | Integration test: full path from raw JSON input → LOs stored in DB; verify Redis cache hit; `POST /dataset/generate` returns partial response (LOs only) |
| **9** | Question Gen | Gemini prompt for **question generation** (PRD §8.3): MCQ (with 4 choices), True/False, Short Answer; structured output per `Question` schema; respect `question_config` counts and `difficulty_distribution` from input |
| **10** | Linking | **Question-to-LO linking** (PRD §8.4): for each question, assign `learning_outcome_id` from the same context's generated LOs; compute `confidence` score; provide `reason` text; semantic similarity fallback if direct mapping fails |
| **11** | Persistence | Persist questions + links to PostgreSQL; Alembic migrations for `questions` and `question_lo_links` tables; batch insert with conflict handling; link each question to at least one LO |
| **12** | Evaluation | **LLM-as-Judge evaluator** (PRD §8.5, Gemini): score each question on 8 criteria: `context_grounding_score`, `clarity_score`, `answer_correctness_score`, `explanation_correctness_score`, `learning_outcome_alignment_score`, `difficulty_score`, `question_type_validity_score`, MCQ `choices_validity_score`; compute `overall_score`; set status: `accepted` / `rejected` / `needs_review`; persist `EvaluationResult` |
| **13** | LangGraph + API | Extend LangGraph: `generate_questions_node → link_outcomes_node → evaluate_node`; conditional edges: `positive_path` (accepted/needs_review) → store; `negative_path` (rejected) → log reason and discard; wire `POST /dataset/evaluate` endpoint; wire full `POST /dataset/generate` |
| **14** | Testing | E2E integration test: JSON input → LOs → Questions → Links → Evaluations stored; all statuses verified; `POST /dataset/generate` and `POST /dataset/evaluate` fully operational |

**Sprint 1 Deliverable ✅**
- `GET /health` ✓
- `POST /dataset/generate` ✓ — full pipeline: LO extraction + question generation + linking
- `POST /dataset/evaluate` ✓ — 8-criteria LLM-as-Judge scoring with accept/reject/needs_review
- LangGraph 5-node pipeline operational
- PostgreSQL storing outcomes, questions, links, evaluations

---

## 🟧 Sprint 2 — Intelligence Layer + Production (Days 15–29)

**Goal**: Export clean dataset, build training pairs, embed questions, fine-tune embedding model, build recommendation, compare base vs fine-tuned quality, harden, and release v0.1.0.

**Sprint 2 endpoints delivered**: `GET /dataset/export` · `POST /training-pairs/build` · `POST /recommendations/questions`

---

### 📅 Week 3 — Dataset Export + Training Pairs + Embeddings + Recommendation (Days 15–21)

| Day | Phase | Tasks |
|---|---|---|
| **15** | Dataset Cleaning | **Dataset cleaning & structuring** (PRD §8.6): filter only `accepted` + `needs_review` records; remove duplicates (exact question text); normalize difficulty values; ensure each record has ≥1 LO link, a correct answer, and an explanation; keep evaluation scores with each record; produce final flat dataset record matching PRD §8.6 example schema |
| **16** | Export | **`GET /dataset/export`** (PRD §9): serialize clean dataset to JSON; include `context_id`, `question_text`, `type`, `choices`, `correct_answer`, `explanation`, `difficulty`, `learning_outcome_ids`, `learning_outcome_texts`, `source_evidence`, `overall_evaluation_score`, `validation_status`; support optional query filters (subject, grade, difficulty) |
| **17** | Training Pairs | **Training pair generation** (PRD §8.7): **Positive pairs** — questions sharing the same generated LO and concept, not exact duplicates → `label: 1, pair_type: "positive"`; **Negative pairs** — questions linked to different LOs → `label: 0, pair_type: "negative"`; **Hard-negative pairs** — questions with similar wording but different LOs → `label: 0, pair_type: "hard_negative"`; persist pairs to DB |
| **18** | Training Pairs | **`POST /training-pairs/build`** (PRD §9): trigger pair generation job; return pair counts (positive / negative / hard-negative); validate pair quality (no duplicate pairs, balanced distribution); export pairs as JSONL for fine-tuning |
| **19** | Embeddings | Integrate `text-embedding-004` (Google, Phase 1 cold-start): generate embeddings for all accepted questions; Redis embedding cache (keyed by question_id + model_version); batch embedding requests |
| **20** | Vector DB | ChromaDB / pgvector integration: upsert question embeddings with metadata (question_id, difficulty, LO IDs, subject); vector similarity search implementation |
| **21** | Recommendation | **`POST /recommendations/questions`** (PRD §8.9 + §9): accept `{"query": "...", "top_k": 5}`; embed query; similarity search in ChromaDB; return top-K with `question_id`, `question_text`, `similarity_score`, `learning_outcome_ids`, `difficulty`; support optional metadata filters |

**Week 3 Checkpoint ✓**: All 6 API endpoints live; training pairs generated; recommendation returns relevant results using base embedding model.

---

### 📅 Week 4 — Fine-Tuning + Recommendation Evaluation + Hardening + Release (Days 22–29)

| Day | Phase | Tasks |
|---|---|---|
| **22** | Fine-Tuning | **Embedding model fine-tuning** (PRD §8.8): use `sentence-transformers` with `MultipleNegativesRankingLoss` or `CosineSimilarityLoss` on generated pairs; no GPU required; checkpoint management; save fine-tuned model artifact |
| **23** | Fine-Tuning | Hot-swap: re-embed all accepted questions with fine-tuned model; update ChromaDB collection; version-tag all embeddings in DB (`embedding_model_version` column); update recommendation endpoint to use fine-tuned model by default |
| **24** | Rec Evaluation | **Recommendation evaluation** (PRD §8.10): run `POST /recommendations/questions` with same queries on both models; compute **Top-K LO match rate** — fraction of top-K results sharing the same LO as the query; count recommendations linked to same LO; produce before-vs-after comparison matching PRD §8.10 example format |
| **25** | Rec Evaluation | Manual relevance review on a 10-question sample; produce evaluation report: base model metrics vs fine-tuned model metrics; export to JSON; log improvement delta; confirm fine-tuning improved Top-K LO match rate |
| **26** | Hardening | Retry logic (exponential backoff for Gemini API + ChromaDB); circuit breaker for Postgres; input size limits (max context length); FastAPI rate limiting; graceful shutdown; structured JSON logging with `request_id` correlation; `422` validation error responses |
| **27** | Testing | Full E2E integration test suite: `pytest` + `httpx` + test DB + in-memory ChromaDB; cover all 6 endpoints; assert Postgres state (LO count, question count, eval status distribution); assert vector store state; assert pair counts |
| **28** | Performance | Load test `POST /dataset/generate` (10 concurrent); measure Redis cache hit rate (target ≥ 70% on repeated inputs); vector search latency (target < 500ms); fix any bottlenecks; seed DB with a real curriculum (e.g., Science Grade 5 Water Cycle from PRD example) |
| **29** | Release | README with setup instructions, `.env.example`, Docker Compose usage, and API examples; Swagger/OpenAPI docs verification; final demo: context → generate → evaluate → export → build pairs → fine-tune → recommend → compare; tag **v0.1.0** |

**Sprint 2 Deliverable ✅**
- `GET /dataset/export` ✓ — clean flat dataset with evaluation scores
- `POST /training-pairs/build` ✓ — positive, negative, hard-negative pairs
- `POST /recommendations/questions` ✓ — base + fine-tuned model supported
- Fine-tuning script + fine-tuned model artifact ✓
- Before-vs-after recommendation comparison (Top-K LO match rate) ✓
- Full test suite passing ✓
- v0.1.0 tagged with README + demo ✓

---

## Summary

| Sprint | Days | Endpoints Delivered | Key Deliverable |
|---|---|---|---|
| **Sprint 1** | 1–14 | `GET /health` · `POST /dataset/generate` · `POST /dataset/evaluate` | Full pipeline: LO extraction → question generation → linking → 8-criteria evaluation |
| **Sprint 2** | 15–29 | `GET /dataset/export` · `POST /training-pairs/build` · `POST /recommendations/questions` | Training pairs → fine-tuned embeddings → recommendation → before/after evaluation → v0.1.0 |

---

## PRD Coverage Checklist

| PRD Section | Sprint | Day |
|---|---|---|
| §8.1 Context Input (JSON schema with question_config + difficulty_distribution) | Sprint 1 | Day 4 |
| §8.2 Learning Outcome Extraction (id, text, concept, source_evidence) | Sprint 1 | Days 5–6 |
| §8.3 Question Generation (MCQ / True-False / Short Answer, full schema) | Sprint 1 | Day 9 |
| §8.4 Question-to-LO Linking (confidence score + reason) | Sprint 1 | Day 10 |
| §8.5 Evaluation Pipeline (8 criteria, LLM-as-Judge, 3 statuses) | Sprint 1 | Days 12–13 |
| §8.6 Dataset Cleaning & Structuring | Sprint 2 | Day 15 |
| §8.7 Training Pair Generation (positive / negative / hard-negative) | Sprint 2 | Days 17–18 |
| §8.8 Embedding Model Fine-Tuning (sentence-transformers, no GPU) | Sprint 2 | Days 22–23 |
| §8.9 Question Recommendation (POST /recommendations/questions) | Sprint 2 | Day 21 |
| §8.10 Recommendation Evaluation (base vs fine-tuned, Top-K LO match rate) | Sprint 2 | Days 24–25 |
| §9 GET /health | Sprint 1 | Day 3 |
| §9 POST /dataset/generate | Sprint 1 | Days 13–14 |
| §9 POST /dataset/evaluate | Sprint 1 | Day 13 |
| §9 GET /dataset/export | Sprint 2 | Day 16 |
| §9 POST /training-pairs/build | Sprint 2 | Day 18 |
| §9 POST /recommendations/questions | Sprint 2 | Day 21 |
| §11 README + final demo + v0.1.0 | Sprint 2 | Day 29 |

> **Buffer note**: Prompt engineering (Days 5, 9, 12) carries the highest variance. Day 8 (integration test) can absorb 1 day of slip by merging with Day 9 morning. Total plan still fits within 29 days.
