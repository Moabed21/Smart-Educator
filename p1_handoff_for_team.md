# P1 Handoff — What's Built, What You Need to Know

> For P2 (AI Engineer) and P3 (Infra/ML Engineer)
> Date: 2024-07-24

---

## Project Structure

```
src/
├── main.py                          ← App entry point, all routers wired
├── .env                             ← Config (DATABASE_URL, GEMINI_API_KEY, etc.)
│
├── helpers/
│   ├── config.py                    ← Settings class (reads .env via pydantic)
│   └── db.py                        ← SQLAlchemy async engine + Base + get_db()
│
├── models/                          ← ORM table definitions (4 tables)
│   ├── learningOutcome.py
│   ├── questions.py
│   ├── questionL0Link.py
│   └── evaluationResult.py
│
├── routes/                          ← All API endpoints
│   ├── base.py                      ← GET /health
│   ├── data.py                      ← POST /upload, POST /process
│   ├── dataset.py                   ← POST /generate, POST /evaluate, GET /export
│   ├── training_pairs.py            ← POST /build
│   ├── recommendations_questions.py ← POST /questions
│   └── schemes/                     ← Pydantic request/response schemas
│       ├── educationalContext.py
│       ├── questions.py
│       ├── learningOutcome.py
│       ├── evaluationResult.py
│       └── questionL0Link.py
│
└── controllers/
    ├── CRUD_Operations/             ← DB read/write functions (ready to use)
    │   ├── learning_outcomes.py
    │   ├── questions.py
    │   ├── question_lo_links.py
    │   └── evaluation_results.py
    ├── DataController.py            ← File upload validation
    ├── ProcessController.py         ← PDF/TXT chunking via LangChain
    └── ProjectController.py         ← File path management
```

---

## API Surface — All 6 Endpoints

| Method | Path | Status | Owner |
|---|---|---|---|
| `GET` | `/api/v1/health` | ✅ Working | P1 |
| `POST` | `/api/v1/data/upload/{project_id}` | ✅ Working | P1 |
| `POST` | `/api/v1/data/process/{project_id}` | ✅ Working | P1 |
| `POST` | `/api/v1/dataset/generate` | ⏳ Stub (needs P2) | P2 wires AI logic |
| `POST` | `/api/v1/dataset/evaluate` | ⏳ Stub (needs P2) | P2 wires LLM-Judge |
| `GET` | `/api/v1/dataset/export` | ⏳ Stub (needs data) | P1 finishes after P2 |
| `POST` | `/api/v1/training-pairs/build` | ⏳ Stub (needs P3) | P3 wires pair logic |
| `POST` | `/api/v1/recommendations/questions` | ⏳ Stub (needs P3) | P3 wires vector search |

---

## Database Tables — What's Created on Startup

All 4 tables auto-create when FastAPI starts via `create_tables()` in `main.py`.

### `learning_outcomes`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `text` | String | Full LO statement |
| `concept` | String | Core concept |
| `source_evidence` | String | Passage excerpt |
| `context_hash` | String (indexed) | `sha256(passage + config)` for dedup |

### `questions`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `question_text` | String | |
| `question_type` | String | `"mcq"` / `"true_false"` / `"short_answer"` |
| `choices` | JSON (nullable) | `["A","B","C","D"]` or NULL |
| `correct_answer` | String | |
| `explanation` | String | |
| `difficulty` | String | `"easy"` / `"medium"` / `"hard"` |
| `estimated_time_minutes` | Integer | |
| `related_LO_ids` | JSON | `["LO_001", "LO_002"]` |
| `source_evidence` | String | |

### `question_lo_links`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `question_id` | UUID (FK → questions) | |
| `lo_id` | UUID (FK → learning_outcomes) | |
| `confidence` | Float | 0.0 – 1.0 |
| `reason` | String | Why this link exists |

### `evaluation_results`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID (PK) | Auto-generated |
| `question_id` | UUID (FK → questions) | |
| 8 score columns | Float | All 0.0 – 1.0, `choices_validity_score` nullable |
| `overall_score` | Float | Weighted average |
| `status` | String | `"accepted"` / `"rejected"` / `"needs_review"` |

---

## CRUD Functions — Ready to Call

### How to use in your code:
```python
from controllers.CRUD_Operations.learning_outcomes import save_outcomes, get_outcomes_by_hash
from controllers.CRUD_Operations.questions import save_questions, get_accepted_questions
from controllers.CRUD_Operations.question_lo_links import save_links, get_links_by_lo
from controllers.CRUD_Operations.evaluation_results import save_evaluations, get_status_counts
```

### Available Functions:

| File | Function | What it does |
|---|---|---|
| `learning_outcomes.py` | `save_outcomes(db, outcomes)` | Bulk insert LOs |
| | `get_outcomes_by_hash(db, hash)` | Check if context already processed |
| | `get_all_outcomes(db)` | Get all LOs |
| `questions.py` | `save_questions(db, questions)` | Bulk insert questions |
| | `get_question_by_id(db, id)` | Single question lookup |
| | `get_all_questions(db)` | All questions (for embedding) |
| | `get_accepted_questions(db)` | Only accepted + needs_review (for export) |
| `question_lo_links.py` | `save_links(db, links)` | Bulk insert links |
| | `get_links_by_question(db, question_id)` | LOs for a question |
| | `get_links_by_lo(db, lo_id)` | Questions for an LO (training pairs!) |
| `evaluation_results.py` | `save_evaluations(db, evals)` | Bulk insert eval results |
| | `get_evaluation_by_question(db, question_id)` | Eval for one question |
| | `get_evaluations_by_status(db, status)` | Filter by status |
| | `get_status_counts(db)` | `{"accepted": 42, ...}` |

All functions take `db: AsyncSession` as first argument. Get the session via `Depends(get_db)` in routes.

---

## Pydantic Schemas — Use These for Gemini Structured Output

```python
# Input payload
from routes.schemes.educationalContext import EducationalContext, QuestionConfig, DifficultyDistribution

# Gemini output schemas
from routes.schemes.learningOutcome import LearningOutcome    # id, text, concept, source_evidence
from routes.schemes.questions import Question, QuestionType    # full question + enum
from routes.schemes.questionL0Link import QuestionL0Link       # confidence, reason
from routes.schemes.evaluationResult import EvaluationResult, EvaluationStatus  # 8 scores + status
```

---

## What P1 Needs From You

### From P2 (AI Engineer):
1. **Wire `POST /dataset/generate`** — call your LangGraph pipeline, use CRUD `save_outcomes()`, `save_questions()`, `save_links()` to persist
2. **Wire `POST /dataset/evaluate`** — call your LLM-Judge, use `save_evaluations()` to persist
3. Once pipeline produces real data → P1 will finish `GET /dataset/export`

### From P3 (Infra/ML Engineer):
1. **Docker Compose running** (PostgreSQL on port 5432) — P1's tables auto-create on startup
2. **Wire `POST /training-pairs/build`** — your pair generator logic, use `get_links_by_lo()` to find positive/negative pairs
3. **Wire `POST /recommendations/questions`** — your vector search logic

---

## How to Run

```bash
cd src/
conda activate Smart-Educator
pip install -r requirements.txt
fastapi dev main.py --reload --port 9999
# Swagger docs at: http://localhost:9999/docs
```

> ⚠️ PostgreSQL must be running on `localhost:5432` with db `smart_educator` before starting.
