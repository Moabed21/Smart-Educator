import json
import uuid
import logging
from typing import Optional
from helpers.db import get_db
from pydantic import BaseModel
from graph.graph import run_pipeline
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

from controllers.CRUD_Operations.questions import get_accepted_questions, get_all_questions, get_questions_by_ids
from controllers.CRUD_Operations.evaluation_results import get_evaluation_by_question, save_evaluations
from controllers.CRUD_Operations.question_lo_links import get_links_by_question
from controllers.CRUD_Operations.learning_outcomes import get_all_outcomes
from helpers.redis_client import get_cached, set_cached
from helpers.hashing import compute_context_hash
from helpers.config import get_settings
from routes.schemes.learningOutcome import LearningOutcome as LearningOutcomePydantic
from models.evaluationResult import EvaluationResult as EvaluationResultORM
from models.questions import Questions as QuestionsORM
from routes.schemes.questions import Question as QuestionPydantic
from routes.schemes.educationalContext import EducationalContext
from routes.schemes.questions import QuestionType
from services.evaluator import evaluate_questions

logger = logging.getLogger("server.routes.dataset")

dataset_router= APIRouter(
    prefix="/api/v1/dataset",
    tags=["dataset"]
)


@dataset_router.post("/generate")
async def generate(payload: EducationalContext, db: AsyncSession = Depends(get_db)):
    """Run the AI pipeline for one educational context."""

    # Checks Redis cache first using context hash. If cached, returns the cached result.
    # Otherwise runs pipeline and caches the result.
    settings = get_settings()
    cache_key = "dataset_generate:" + compute_context_hash(payload)
    try:
        cached_result = await get_cached(cache_key)
        if cached_result is not None:
            logger.info("Serving /dataset/generate response from Redis cache.")
            return json.loads(cached_result)
    except Exception as exc:
        logger.warning("Redis cache check failed: %s", exc)

    try:
        final_state = await run_pipeline(payload, db)
    except Exception as exc:
        logger.error("AI pipeline failed for /dataset/generate", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI pipeline failed: {exc}",
        )

    result = {
        "learning_outcomes_created": final_state["persisted_learning_outcomes"],
        "questions_created": final_state["persisted_questions"],
        "links_created": final_state["persisted_links"],
        "evaluations_created": final_state["persisted_evaluations"],
        "questions_discarded": final_state["discarded_count"],
        "status_breakdown": final_state["status_breakdown"],
    }
    # the storing of the context in redis for 24 hours(86400)
    try:
        await set_cached(cache_key, json.dumps(result), ttl_seconds=settings.REDIS_TTL)
    except Exception as exc:
        logger.warning("Redis cache write failed: %s", exc)

    return result

class EvaluateRequest(BaseModel):
    """Optional body for POST /dataset/evaluate.

    question_ids: specific question UUIDs (as strings) to re-evaluate. If
    omitted (or the whole body is omitted), every question in the DB that
    doesn't yet have an evaluation_results row is evaluated instead.
    """

    question_ids: Optional[list[str]] = None


async def _fetch_questions_to_evaluate(
    db: AsyncSession, question_ids: Optional[list[str]]
) -> list[QuestionsORM]:
    """Resolve the request into concrete ORM Questions rows to re-evaluate.

    Explicit ids: fetched via get_question_by_id, one at a time (no bulk-by-id
    CRUD exists). Malformed ids and ids with no matching row are skipped with
    a warning, not raised — a single bad id in a batch shouldn't block the rest.

    No ids given: get_all_questions() then filtered, one get_evaluation_by_question
    call per question, to those with no existing evaluation_results row yet.
    This is N+1 queries — acceptable at this dataset's scale, and deliberately
    reuses existing CRUD functions rather than adding a new bulk query.
    """
    if question_ids:
        valid_uuids = []
        for raw_id in question_ids:
            try:
                valid_uuids.append(uuid.UUID(raw_id))
            except ValueError:
                logger.warning("Skipping malformed question id %r in /dataset/evaluate request.", raw_id)
        return await get_questions_by_ids(db, valid_uuids)

    all_questions = await get_all_questions(db)
    unevaluated = []
    for question in all_questions:
        try:
            existing = await get_evaluation_by_question(db, question.id)
        except MultipleResultsFound:
            # get_evaluation_by_question assumes at most one evaluation per
            # question (uses scalar_one_or_none()), but re-evaluation via
            # explicit question_ids is insert-only (no upsert) and can leave
            # a question with 2+ evaluation_results rows on purpose, to keep
            # history. More than one row unambiguously means "already
            # evaluated" — treat it the same as a single existing row.
            existing = True
        if existing is None:
            unevaluated.append(question)
    return unevaluated


async def _build_pydantic_pairs(
    db: AsyncSession, orm_questions: list[QuestionsORM]
) -> tuple[list[QuestionPydantic], list[LearningOutcomePydantic], dict[int, QuestionsORM]]:
    """Reconstruct Pydantic Question/LearningOutcome objects that evaluate_questions() expects.

    IMPORTANT: `Questions.related_LO_ids` (the JSON column) still holds the
    ORIGINAL Gemini-time `LO_001`-style labels from generation time — those
    labels were discarded once the real LearningOutcome rows were saved
    (see generate()'s comments) and no longer correspond to anything. Using
    them here would make every question look like it has zero valid LO
    context to evaluate_questions() (which matches `related_LO_ids` strings
    against `LearningOutcome.id`). So `related_LO_ids` is rebuilt here from
    the REAL, saved `QuestionLOLink` rows instead — using `str(real UUID)`
    consistently as the id on both the reconstructed Question and the
    reconstructed LearningOutcome, so evaluate_questions()'s internal lookup
    actually finds a match.
    """
    all_outcomes_by_id = {lo.id: lo for lo in await get_all_outcomes(db)}

    pydantic_questions: list[QuestionPydantic] = []
    question_identity_to_orm: dict[int, QuestionsORM] = {}
    lo_pydantic_by_str_id: dict[str, LearningOutcomePydantic] = {}

    for orm_question in orm_questions:
        links = await get_links_by_question(db, orm_question.id)
        related_lo_ids: list[str] = []
        for link in links:
            orm_lo = all_outcomes_by_id.get(link.lo_id)
            if orm_lo is None:
                logger.warning(
                    "QuestionLOLink references missing LO id=%s for question id=%s — skipping.",
                    link.lo_id, orm_question.id,
                )
                continue
            lo_str_id = str(orm_lo.id)
            related_lo_ids.append(lo_str_id)
            if lo_str_id not in lo_pydantic_by_str_id:
                lo_pydantic_by_str_id[lo_str_id] = LearningOutcomePydantic(
                    id=lo_str_id,
                    text=orm_lo.text,
                    concept=orm_lo.concept,
                    source_evidence=orm_lo.source_evidence,
                )

        pydantic_question = QuestionPydantic(
            question_text=orm_question.question_text,
            question_type=QuestionType(orm_question.question_type),
            choices=orm_question.choices,
            correct_answer=orm_question.correct_answer,
            explanation=orm_question.explanation,
            difficulty=orm_question.difficulty,
            estimated_time_minutes=orm_question.estimated_time_minutes,
            related_LO_ids=related_lo_ids,
            source_evidence=orm_question.source_evidence,
        )
        pydantic_questions.append(pydantic_question)
        question_identity_to_orm[id(pydantic_question)] = orm_question

    return pydantic_questions, list(lo_pydantic_by_str_id.values()), question_identity_to_orm


@dataset_router.post("/evaluate")
async def evaluate(payload: EvaluateRequest | None = None, db: AsyncSession = Depends(get_db)):
    """Re-evaluate questions that already exist in the DB.

    Unlike generate(), this does NOT call LO extraction or question
    generation — it only re-runs the LLM-as-judge pass (services/evaluator.py)
    against already-saved questions, either specific ones (`question_ids`) or
    every question that doesn't yet have an evaluation_results row.
    """
    orm_questions = await _fetch_questions_to_evaluate(db, payload.question_ids if payload else None)

    if not orm_questions:
        return {
            "questions_evaluated": 0,
            "status_breakdown": {"accepted": 0, "needs_review": 0, "rejected": 0},
        }

    try:
        pydantic_questions, pydantic_outcomes, question_identity_to_orm = await _build_pydantic_pairs(
            db, orm_questions
        )
        evaluations = await evaluate_questions(pydantic_questions, pydantic_outcomes)
    except Exception as exc:
        logger.error("Evaluation failed for /dataset/evaluate", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {exc}",
        )

    try:
        orm_evaluations = []
        for evaluation in evaluations:
            orm_question = question_identity_to_orm.get(id(evaluation.question))
            if orm_question is None:
                logger.warning(
                    "Skipping unresolvable evaluation (question_text=%r) — "
                    "no matching saved ORM question found.",
                    evaluation.question.question_text,
                )
                continue
            r = evaluation.result
            orm_evaluations.append(
                EvaluationResultORM(
                    question_id=orm_question.id,
                    context_grounding_score=r.context_grounding_score,
                    clarity_score=r.clarity_score,
                    answer_correctness_score=r.answer_correctness_score,
                    explanation_correctness_score=r.explanation_correctness_score,
                    learning_outcome_alignment_score=r.learning_outcome_alignment_score,
                    difficulty_score=r.difficulty_score,
                    question_type_validity_score=r.question_type_validity_score,
                    choices_validity_score=r.choices_validity_score,
                    overall_score=r.overall_score,
                    status=r.status.value,
                )
            )
        await save_evaluations(db, orm_evaluations)
    except Exception as exc:
        logger.error("Persistence failed for /dataset/evaluate", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Persistence failed: {exc}",
        )

    status_breakdown = {"accepted": 0, "needs_review": 0, "rejected": 0}
    for evaluation in evaluations:
        status_breakdown[evaluation.result.status.value] += 1

    return {
        "questions_evaluated": len(orm_evaluations),
        "status_breakdown": status_breakdown,
    }

@dataset_router.get("/export")
async def export(
    difficulty: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Export clean dataset containing accepted and needs_review records.

    Filters questions by difficulty if provided. Includes learning outcome texts,
    evaluation score, and validation status.
    """
    accepted_questions = await get_accepted_questions(db)
    if difficulty:
        accepted_questions = [q for q in accepted_questions if q.difficulty == difficulty]

    all_outcomes = {lo.id: lo for lo in await get_all_outcomes(db)}
    records = []

    for q in accepted_questions:
        links = await get_links_by_question(db, q.id)
        linked_los = [all_outcomes.get(link.lo_id) for link in links if link.lo_id in all_outcomes]

        try:
            eval_res = await get_evaluation_by_question(db, q.id)
        except MultipleResultsFound:
            eval_res = None

        record = {
            "question_id": str(q.id),
            "question_text": q.question_text,
            "question_type": q.question_type,
            "choices": q.choices,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "estimated_time_minutes": q.estimated_time_minutes,
            "learning_outcome_ids": [str(link.lo_id) for link in links],
            "learning_outcome_texts": [lo.text for lo in linked_los if lo],
            "source_evidence": q.source_evidence,
            "overall_evaluation_score": eval_res.overall_score if eval_res else None,
            "validation_status": eval_res.status if eval_res else "needs_review",
        }
        records.append(record)

    return records
