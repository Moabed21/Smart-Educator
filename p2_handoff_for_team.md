# P2 Handoff — What's Built, What You Need to Know

> For P1 (API & Data Engineer) and P3 (Infra/ML Engineer)
> Date: 2026-07-25

---

## Summary

The full AI pipeline is built, wired into real API endpoints, and verified against a **live Gemini API + live PostgreSQL** — not mocked. Today's testing used the real "Bohr's hydrogen atom" chemistry passage (Arabic) end to end:

- `POST /api/v1/dataset/generate` — ✅ working. Full run: 5 LOs → 7 questions → 7 links → 7 evaluations, all persisted with real UUIDs and correct foreign keys, confirmed via direct PostgreSQL queries (row counts went 0→5/0→7/0→7/0→7, not just an in-memory success). **Updated today: rejected questions are no longer persisted** — `graph/graph.py`'s `store_node` only saves accepted/needs_review questions (and their links/evaluations); an all-rejected batch touches the DB not at all. Verified with a mixed-batch test (1 deliberately-corrupted MCQ + 6 normal questions): the rejected one was confirmed absent from the `questions` table via direct SQL query, the other 6 persisted normally.
- `POST /api/v1/dataset/evaluate` — ✅ working. Re-evaluates already-saved questions (no LO extraction / question generation involved). Tested both the "evaluate everything unevaluated" path and explicit `question_ids` re-evaluation; hit and fixed one real bug along the way (see Known Gaps).
- `GET /api/v1/dataset/export` — still P1's stub, untouched.

All 4 AI services (`gemini_client`, `lo_extraction`, `question_generator`, `lo_linker`, `evaluator`) and the LangGraph pipeline (`graph/graph.py`) were tested individually before being wired into the endpoints — not just tested as one black box.

---

## Project Structure — What I Added

```
src/
├── graph/
│   ├── __init__.py
│   └── graph.py                      ← LangGraph pipeline: run_pipeline()
│
├── services/
│   ├── gemini_client.py              ← Gemini SDK wrapper (retry + validation + structured output)
│   ├── lo_extraction.py              ← extract_learning_outcomes()
│   ├── question_generator.py         ← generate_questions()
│   ├── lo_linker.py                  ← link_questions_to_outcomes() (embedding similarity, no Gemini call)
│   └── evaluator.py                  ← evaluate_questions() (LLM-as-judge, separate Gemini pass)
│
├── routes/
│   └── dataset.py                    ← filled in: POST /generate, POST /evaluate (GET /export still P1's stub)
│
└── test_lo_extraction_manual.py      ← manual smoke test, calls run_pipeline() against real Gemini API
```

---

## The Services

### `services/gemini_client.py`
```python
async def generate_structured_output(prompt: str, response_schema: type, max_output_tokens: int = 16384)
```
Wraps Gemini structured-output calls. Retries up to 3 attempts (2s → 4s → 8s backoff) on transient errors (HTTP 429/500/502/503/504) and on `pydantic.ValidationError` (treated as a one-off generation slip, not a persistent failure). Raises immediately (no retry) on non-retryable HTTP codes (400/401/403/404) and on `MAX_TOKENS` truncation. Returns the response already parsed and validated into `response_schema` via `pydantic.TypeAdapter` — callers never touch raw JSON.

**Verified today:** ran successfully dozens of times against the real API across every other service. Confirmed the retry loop actually retries on a real `429 RESOURCE_EXHAUSTED` (hit the free-tier daily quota mid-session) and raises cleanly after exhausting attempts.

**Important — uses `google-genai`, not `google-generativeai`.** See "Known Gaps" below — this was a deliberate mid-session migration after finding 2 real bugs in the old SDK.

### `services/lo_extraction.py`
```python
async def extract_learning_outcomes(context: EducationalContext) -> list[LearningOutcome]
```
Builds an English-instruction prompt (Arabic output for `text`/`concept`/`source_evidence`), calls `generate_structured_output` with `list[LearningOutcome]`. Prompt enforces: one skill per LO, sequential `LO_001`-style ids, `source_evidence` must be an exact verbatim passage quote, no fabrication, all 4 fields always present.

**Verified today:** ran against the real chemistry passage, produced 4-6 LOs per run (varies slightly by generation), all fields populated, `source_evidence` spot-checked as exact substrings of the source passage.

### `services/question_generator.py`
```python
async def generate_questions(context: EducationalContext, learning_outcomes: list[LearningOutcome]) -> list[Question]
```
Generates exactly `question_config.mcq_count`/`true_false_count`/`short_answer_count` questions, roughly matching `difficulty_distribution`. Every question must cite at least one real `LO_XXX` id from the given list. MCQ = exactly 4 choices; true/false and short-answer = `choices: null`.

**Verified today:** consistently produced the exact requested counts (e.g. 3 MCQ + 2 T/F + 2 short-answer = 7), all MCQs had exactly 4 choices with `correct_answer` matching one of them, `choices=null` correctly on non-MCQ.

### `services/lo_linker.py`
```python
async def link_questions_to_outcomes(questions: list[Question], learning_outcomes: list[LearningOutcome]) -> list[ResolvedLink]
```
**Not a Gemini call** — pure local embedding similarity via `sentence-transformers` (`paraphrase-multilingual-mpnet-base-v2`, chosen for Arabic support). For each `(question, claimed LO id)` pair, resolves the real `LearningOutcome`, skips (logs a warning, doesn't crash) any invented id Gemini didn't actually extract, then scores cosine similarity between `question_text` and `learning_outcome.text` (batched into 2 `encode()` calls, run via `asyncio.to_thread` so it doesn't block the event loop). `ResolvedLink` is a dataclass (`question`, `learning_outcome`, `link: QuestionL0Link`) since `QuestionL0Link` itself has no id fields to carry the relationship (see Known Gaps).

**Verified today:** deliberately injected an invented LO id into a question's `related_LO_ids` — confirmed it logs a clear warning and skips just that one link while the question's other, real LO id still resolves normally (no crash, no cascading failure). Model load + score for 7-8 pairs took 5-9s on CPU.

### `services/evaluator.py`
```python
async def evaluate_questions(questions: list[Question], learning_outcomes: list[LearningOutcome]) -> list[ResolvedEvaluation]
```
LLM-as-judge — **deliberately a separate Gemini call from question generation**, so the model isn't grading its own work. All questions for one context are judged in a **single batched Gemini call** (not one call per question) to conserve quota/cost/latency. Scores the 8 PRD criteria per question, then:
- `overall_score` = simple equal-weight average of the applicable scores (documented assumption — PRD doesn't specify weights).
- `status` thresholds per `team_strategy.md`: `accepted ≥0.75`, `needs_review 0.5–0.74`, `rejected <0.5`.
- **Hard override (my own design decision, not in the PRD):** if `answer_correctness_score < 0.5`, `status` is forced to `rejected` regardless of the averaged `overall_score` — a factually wrong answer must never land in `needs_review` just because other criteria happened to score well.

`ResolvedEvaluation` dataclass (`question`, `result: EvaluationResult`) — same reasoning as `ResolvedLink`, since `EvaluationResult` has no `question_id` field either.

**Verified today, rigorously — not just "it ran":**
1. First run on real generated questions: all 8 criteria came back a flat 1.0 on every question. Flagged this as suspicious (looked like model sycophancy, not real judgment) rather than accepting it at face value.
2. Injected a deliberately wrong `correct_answer` into a real MCQ (swapped to a wrong choice, left `explanation`/`source_evidence` pointing at the real answer). Evaluator correctly caught it: `answer_correctness_score=0.0`, `explanation_correctness_score=0.0`, `choices_validity_score=0.0` — proving it does discriminate, the earlier all-1.0 run was genuinely 7 well-formed questions, not a broken judge.
3. Before the hard override existed, that corrupted question landed at `overall_score=0.625` → `needs_review` (diluted by 6 other passing criteria). Added the override, re-ran, confirmed `status=rejected` this time, `overall_score` unchanged (still the honest average, for transparency).

### `graph/graph.py`
```python
class GraphState(TypedDict):
    context: EducationalContext
    db: AsyncSession
    context_hash: str
    learning_outcomes: list[LearningOutcome]
    questions: list[Question]
    resolved_links: list[ResolvedLink]
    evaluations: list[ResolvedEvaluation]
    persisted_learning_outcomes: int
    persisted_questions: int
    persisted_links: int
    persisted_evaluations: int
    discarded_count: int
    status_breakdown: dict

async def run_pipeline(context: EducationalContext, db: AsyncSession) -> GraphState
```
**Updated today (Gap 2 fix) — no longer a plain linear chain.** Flow is now:
```
parse -> extract_outcomes -> generate_questions -> link_outcomes -> evaluate
    -> [conditional: route_after_evaluate] -> store -> END
                                            -> log_and_discard -> END
```
- `parse_node` computes `context_hash` up front (`compute_context_hash()`, moved here from `routes/dataset.py` — see Known Gaps #4, now resolved).
- `extract_outcomes`/`generate_questions`/`link_outcomes`/`evaluate` are unchanged from before — thin wrappers around the 4 services, each re-raising failures as `RuntimeError` with stage-specific context.
- `route_after_evaluate` (conditional edge): `"store"` if **any** evaluation is `accepted`/`needs_review`, else `"discard"` — only an all-`rejected` batch skips persistence entirely.
- `store_node` now **owns all persistence** (moved out of `routes/dataset.py` — see endpoint section below): saves every `LearningOutcome` unconditionally, but filters `Questions`/`QuestionLOLink`/`EvaluationResult` down to only the accepted/needs_review questions. Rejected questions in a mixed batch are logged (`question_text`, `overall_score`, `answer_correctness_score`) and skipped individually — they never reach `save_questions`/`save_links`/`save_evaluations`.
- `log_and_discard_node` runs only when the entire batch was rejected — logs each rejection, **touches the DB not at all** (not even `LearningOutcomes`).
- `db: AsyncSession` is now carried in `GraphState` itself (not passed as a separate argument), since LangGraph nodes only ever receive `state` — this is how `store_node` gets a session. Safe because no checkpointer is configured (state is never serialized between runs).
- `run_pipeline(context, db)` signature changed — now takes `db` too, and returns `persisted_*`/`discarded_count`/`status_breakdown` in the final state for the route to read directly.

**Verified today:** two full-pipeline test runs.
1. Plain run (no injected defects): 5 LOs → 7 questions → 7 links → 7 evaluations, all `accepted`, routed to `store`, all persisted, `discarded=0` — identical behavior to before the refactor.
2. **Mixed-batch rejection test**: deliberately corrupted one MCQ's `correct_answer` (swapped to a wrong choice) before the `evaluate` stage. Evaluator caught it (`answer_correctness_score=0.0`, `status=rejected`, `overall_score=0.625`), `route_after_evaluate` still returned `"store"` (6 of 7 savable), and `store_node` persisted `LOs=5, questions=6, links=6, evaluations=6`, `discarded=1`. **Confirmed via direct PostgreSQL query**: `SELECT COUNT(*) FROM questions WHERE correct_answer = '<the corrupted wrong answer>'` → `0`. The corrupted question never reached the `questions` table.

Per-node `RuntimeError` wrapping (for the 4 AI-service nodes) still hasn't been exercised by a real failure — only the store/discard branch has been proven this way.

---

## The Two Live Endpoints

### `POST /api/v1/dataset/generate`
**Input:** `EducationalContext` (subject, grade_level, passage, question_config, difficulty_distribution) as the request body.

**Updated today (Gap 2 fix) — the route no longer does any persistence itself.** It now just calls `run_pipeline(payload, db)` and reads the response off the final `GraphState`:
```python
final_state = await run_pipeline(payload, db)
return {
    "learning_outcomes_created": final_state["persisted_learning_outcomes"],
    "questions_created": final_state["persisted_questions"],
    "links_created": final_state["persisted_links"],
    "evaluations_created": final_state["persisted_evaluations"],
    "questions_discarded": final_state["discarded_count"],
    "status_breakdown": final_state["status_breakdown"],
}
```
All the Pydantic→ORM conversion and `save_outcomes`/`save_questions`/`save_links`/`save_evaluations` calls described in earlier versions of this doc now live in `graph/graph.py`'s `store_node` (see "The Services" section above) — **not** here. The route's only remaining job is calling the pipeline and reporting what it says happened; on any AI-pipeline failure it still wraps the exception in a `500` the same way as before.

**Rejected questions are no longer persisted at all.** Previously every question — accepted or rejected — was saved unconditionally. Now `store_node` only saves `accepted`/`needs_review` questions (and their links/evaluations); an all-`rejected` batch touches the DB not at all (`log_and_discard_node`). See the `graph/graph.py` section above for the exact mixed-batch test that verified this (corrupted MCQ → `rejected` → confirmed absent from `questions` via direct SQL query).

**Confirmed via direct PostgreSQL query today:** before the first call, all 4 tables (`learning_outcomes`, `questions`, `question_lo_links`, `evaluation_results`) were empty (0 rows each). After one `POST` with the real chemistry passage: 5/7/7/7 rows respectively, response body `{"learning_outcomes_created":5,"questions_created":7,"links_created":7,"evaluations_created":7,"status_breakdown":{"accepted":7,"needs_review":0,"rejected":0}}` — same shape of result as before the refactor, since that run was all-accepted. Cross-checked FK integrity directly: every `question_lo_links.question_id`/`lo_id` and `evaluation_results.question_id` matched a real row in `questions`/`learning_outcomes`. Arabic content confirmed intact via UTF-8 read (`concept: الطيف المرئي`, etc. — not corrupted, just displays as `????` in a non-UTF-8 terminal).

### `POST /api/v1/dataset/evaluate`
**Input (optional body):** `{"question_ids": ["<uuid>", ...]}` or nothing/`{}`.

**What it does — does NOT call LO extraction or question generation, only re-runs the judge on already-saved questions:**
1. If `question_ids` given: fetches each via `get_question_by_id`, skipping malformed/missing ids with a warning.
2. If not given: `get_all_questions()`, filtered down to ones with no existing `evaluation_results` row yet.
3. For each fetched question: rebuilds Pydantic `Question`/`LearningOutcome` objects from the ORM rows — **important detail**: `related_LO_ids` is rebuilt from the real, saved `QuestionLOLink` rows (via `get_links_by_question`), not from the stale `LO_001`-style JSON blob on the question (that label no longer corresponds to anything once the real LO was saved — see Known Gaps).
4. `evaluate_questions(...)` on the reconstructed pairs.
5. Converts results to ORM `EvaluationResult` rows (`question_id` = the real already-saved UUID), `save_evaluations(db, ...)`.
6. Returns `{"questions_evaluated": N, "status_breakdown": {...}}`.

**Confirmed via direct PostgreSQL query today, two scenarios:**
- Empty body: all 11 questions in the DB already had an evaluation → response `{"questions_evaluated":0,...}`. Correct — proves the filter works, not just a pass-through.
- Explicit `question_ids` for 2 already-evaluated questions (forcing re-evaluation): response `{"questions_evaluated":2,"status_breakdown":{"accepted":2,...}}`. `evaluation_results` row count went **11 → 13** (confirmed via query) — both re-evaluated questions now have 2 evaluation rows each (old + new), since `save_evaluations` only inserts, never upserts.
- **Bug found and fixed live**: the "already evaluated?" check (`get_evaluation_by_question`, which uses `scalar_one_or_none()`) throws `MultipleResultsFound` once a question has 2+ evaluation rows — which the above re-evaluation test itself caused. This crashed the empty-body path with a 500 the next time it ran. Fixed by catching `MultipleResultsFound` in my own filtering code and treating it the same as "already evaluated." Re-tested, confirmed clean `200` afterward.

---

## Known Gaps / Design Decisions — Flagging to P1 and P3

1. **`QuestionL0Link` and `EvaluationResult` Pydantic schemas have no `question_id`/`lo_id` fields** (`routes/schemes/questionL0Link.py` is literally just `confidence` + `reason`; same situation for `EvaluationResult`). I worked around this with `ResolvedLink`/`ResolvedEvaluation` dataclasses that carry the full objects alongside the link/result, and with object-identity matching in `routes/dataset.py` (since `Question` also has no id field at all). This works, but if either of you touch these schemas, know that the id fields were never there to begin with — not an oversight I introduced.

2. **Gemini SDK migration: `google-generativeai` → `google-genai`.** Found 2 real bugs in the old SDK's automatic Pydantic-schema conversion mid-session: it raises on any field with a Python default value (`Optional[X] = None`), and separately silently drops properties past a certain point in models with several fields/an enum/a list — causing Gemini to dump missing fields as raw text into the last known field instead of separate JSON keys. Migrated `gemini_client.py` and `requirements.txt` to `google-genai` (confirmed `langchain-google-genai` already depends on `google-genai`, not the old package, so no conflict). If either of you write anything that touches Gemini directly, use `google.genai`, not `google.generativeai`.

3. **Model is currently `gemini-flash-lite-latest`, not `gemini-flash-latest`** (`services/gemini_client.py`, `_MODEL_NAME`). This was a deliberate temporary swap today to stay under the free-tier's 20-req/day quota on `gemini-flash-latest` (hit a real `429` on it earlier). **This needs to be switched back to `gemini-flash-latest` before considering the pipeline "production-configured"** — it's a one-line change, just don't forget it's currently pointed at the lite model.

4. **`_compute_context_hash` in `routes/dataset.py` duplicates logic P3 will eventually need for Redis caching.** Per `team_strategy.md`'s Day-4 plan, the Redis cache key is meant to be the same `sha256(context + question_config)`. Right now it's only computed inline in `dataset.py` for the DB dedup column. Once P3's Redis layer exists, this should move to a shared helper (e.g. `helpers/hashing.py`) both call — flagged with a TODO comment in the code already.

5. **`generate()` has no idempotency check** — it doesn't call `get_outcomes_by_hash` before running the pipeline, so POSTing the same passage twice creates fully duplicate LOs/questions/links/evaluations rather than reusing existing ones. This is presumably P3's Redis-cache-hit responsibility per the sprint plan, not something I added.

6. **`save_evaluations` is insert-only (no upsert exists anywhere in the CRUD layer)** — re-evaluating a question always adds a new row rather than replacing the old one, by design (keeps history), but this is what caused the `MultipleResultsFound` bug above. If P1 ever wants "latest evaluation only" semantics, that's a CRUD-layer decision, not something I should silently change.

7. **Docker is still not actually running for this project.** Docker Desktop itself wasn't running in this environment; PostgreSQL 18.4 is running **natively on Windows**, not via `docker-compose.yml` (which is still the empty file P1's handoff already flagged). Everything I tested today was against this native install — P3's Docker Compose deliverable is still outstanding and untested.

8. **Environment/deps note**: `requirements.txt` didn't include `fastapi[standard]` (needed for `uvicorn`/`fastapi dev` to actually run) — I installed it ad hoc to test, but it's not yet added to `requirements.txt`. Also: no conda env was available in my environment despite the original handoff's `conda activate Smart-Educator` instruction — I installed everything into system Python instead. Worth confirming the team's actual dev setup matches what's in `requirements.txt` before others rely on it.

9. **Stray empty file at repo root**: `graph/graph.py` (outside `src/`, not the one I built at `src/graph/graph.py`). Not importable from where the app actually runs — safe to delete once confirmed it wasn't meant for something else.

10. **Persistence in `store_node` is NOT wrapped in one atomic transaction.** `save_outcomes` → `save_questions` → `save_links` → `save_evaluations` are 4 separate `add_all()`+`commit()` calls (each CRUD function commits on its own). If, say, `save_links` raised partway through, the `LearningOutcomes` and `Questions` already committed in the earlier calls would stay persisted while links/evaluations wouldn't — a partial write, not a clean all-or-nothing rollback. This isn't a regression from today's refactor (the old inline code in `routes/dataset.py` had the exact same non-atomicity, just spread across the route instead of `store_node`) — just now more visible since it's now clearly one node's responsibility. If this matters for correctness later, it needs an explicit transaction wrapping all 4 saves (e.g. a single `db.begin()` block with commits/flushes deferred to the end), which none of the CRUD functions currently support (each one always calls `commit()` itself).

---

## How to Run / Test

```bash
cd src/
pip install -r requirements.txt
pip install "fastapi[standard]"   # not yet in requirements.txt, see Known Gaps #8
python -m uvicorn main:app --port 9999
# Swagger docs at: http://localhost:9999/docs
```

> ⚠️ PostgreSQL must be running on `localhost:5432` with db `smart_educator` before starting (see Known Gaps #7 — not via Docker in my environment today).
> ⚠️ `services/gemini_client.py` is currently pointed at `gemini-flash-lite-latest` — switch to `gemini-flash-latest` once you're past today's quota concerns (see Known Gaps #3).

**Manual pipeline smoke test (no HTTP, calls `run_pipeline()` directly against the real Gemini API):**
```bash
cd src/
python test_lo_extraction_manual.py
```
Note: `run_pipeline()` now requires a `db: AsyncSession` argument (see `graph/graph.py` section above) — the test script opens one itself via `helpers.db.AsyncSessionLocal()`. This means running this script now **actually persists to Postgres** (through `store_node`), it's no longer a DB-free service-level smoke test like it was earlier today.

**Test the live endpoints via Swagger** (`/docs`) or `curl`/Python `httpx` against:
- `POST /api/v1/dataset/generate` — body: `EducationalContext` JSON (see `routes/schemes/educationalContext.py` for the exact shape).
- `POST /api/v1/dataset/evaluate` — body optional: `{"question_ids": [...]}` or `{}`/nothing.
