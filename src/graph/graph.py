"""LangGraph pipeline wiring the 4 AI services into one linear flow, plus
conditional accept/discard persistence.

parse -> extract_outcomes -> generate_questions -> link_outcomes -> evaluate
    -> [conditional] -> store -> END
                      -> log_and_discard -> END

Each service-calling node is a thin wrapper around one already-tested service
call (lo_extraction, question_generator, lo_linker, evaluator) — no business
logic lives there beyond per-stage error context. `store`/`log_and_discard`
own ALL persistence: whether any DB write happens at all is decided by the
conditional edge after `evaluate`, not by routes/dataset.py, which now only
calls `run_pipeline()` and reports whatever the final state says was
persisted/discarded.
"""
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from crud.evaluation_results import save_evaluations
from crud.learning_outcomes import save_outcomes
from crud.question_lo_links import save_links
from crud.questions import save_questions
from helpers.hashing import compute_context_hash
from models.evaluationResult import EvaluationResult as EvaluationResultORM
from models.learningOutcome import LearningOutcome as LearningOutcomeORM
from models.questionL0Link import QuestionLOLink as QuestionLOLinkORM
from models.questions import Questions as QuestionsORM
from routes.schemes.educationalContext import EducationalContext
from routes.schemes.evaluationResult import EvaluationStatus
from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questions import Question
from services.evaluator import ResolvedEvaluation, evaluate_questions
from services.lo_extraction import extract_learning_outcomes
from services.lo_linker import ResolvedLink, link_questions_to_outcomes
from services.question_generator import generate_questions

logger = logging.getLogger("server.graph")

_KEEP_STATUSES = (EvaluationStatus.ACCEPTED, EvaluationStatus.NEEDS_REVIEW)


class GraphState(TypedDict):
    """Pipeline state threaded through every node.

    `db` is carried in state (not passed as a separate node argument) because
    LangGraph nodes only ever receive `state` — this is the pragmatic way for
    `store_node` to get a DB session without changing the node-calling
    convention. No checkpointer is configured on this graph, so a live
    `AsyncSession` living in state for the duration of one `ainvoke()` call is
    safe — state is never serialized or persisted between runs.

    `persisted_*`/`discarded_count`/`status_breakdown` start at 0/empty and
    are populated by whichever of `store_node`/`log_and_discard_node` runs —
    `routes/dataset.py` reads these directly instead of doing any persistence
    itself.
    """

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


async def parse_node(state: GraphState) -> dict:
    """Compute context_hash up front, before any Gemini calls."""
    return {"context_hash": compute_context_hash(state["context"])}


async def extract_outcomes_node(state: GraphState) -> dict:
    """Call `extract_learning_outcomes` on `state["context"]`, store the result."""
    context = state["context"]
    try:
        learning_outcomes = await extract_learning_outcomes(context)
    except Exception as exc:
        raise RuntimeError(
            f"LO extraction failed for context (subject={context.subject!r}, "
            f"grade_level={context.grade_level!r}): {exc}"
        ) from exc
    return {"learning_outcomes": learning_outcomes}


async def generate_questions_node(state: GraphState) -> dict:
    """Call `generate_questions` using the context + LOs already in state."""
    context = state["context"]
    learning_outcomes = state["learning_outcomes"]
    try:
        questions = await generate_questions(context, learning_outcomes)
    except Exception as exc:
        raise RuntimeError(
            f"Question generation failed for context (subject={context.subject!r}) "
            f"with {len(learning_outcomes)} LOs available: {exc}"
        ) from exc
    return {"questions": questions}


async def link_outcomes_node(state: GraphState) -> dict:
    """Call `link_questions_to_outcomes` using the questions + LOs in state."""
    questions = state["questions"]
    learning_outcomes = state["learning_outcomes"]
    try:
        resolved_links = await link_questions_to_outcomes(questions, learning_outcomes)
    except Exception as exc:
        raise RuntimeError(
            f"LO linking failed for {len(questions)} questions against "
            f"{len(learning_outcomes)} LOs: {exc}"
        ) from exc
    return {"resolved_links": resolved_links}


async def evaluate_node(state: GraphState) -> dict:
    """Call `evaluate_questions` using the questions + LOs in state."""
    questions = state["questions"]
    learning_outcomes = state["learning_outcomes"]
    try:
        evaluations = await evaluate_questions(questions, learning_outcomes)
    except Exception as exc:
        raise RuntimeError(
            f"Evaluation failed for {len(questions)} questions: {exc}"
        ) from exc
    return {"evaluations": evaluations}


def route_after_evaluate(state: GraphState) -> str:
    """"store" if ANY question is accepted/needs_review, else "discard" —
    the all-rejected case is the only one that skips the DB entirely."""
    if any(evaluation.result.status in _KEEP_STATUSES for evaluation in state["evaluations"]):
        return "store"
    return "discard"


async def store_node(state: GraphState) -> dict:
    """Persist LearningOutcomes (all of them) + ONLY the accepted/needs_review
    Questions (and their corresponding QuestionLOLink/EvaluationResult rows).

    Rejected questions in a mixed batch are logged and skipped individually
    here — they never reach save_questions/save_links/save_evaluations, so
    they never appear in the questions table. LearningOutcomes are saved
    unconditionally: an LO isn't itself accepted/rejected, and dropping one
    could orphan a link needed by an accepted question that shares it.
    """
    db = state["db"]
    context_hash = state["context_hash"]
    learning_outcomes = state["learning_outcomes"]
    questions = state["questions"]
    resolved_links = state["resolved_links"]
    evaluations = state["evaluations"]

    kept_question_ids: set[int] = set()
    rejected_evaluations = []
    for evaluation in evaluations:
        if evaluation.result.status in _KEEP_STATUSES:
            kept_question_ids.add(id(evaluation.question))
        else:
            rejected_evaluations.append(evaluation)

    if rejected_evaluations:
        logger.info(
            "Discarding %d rejected question(s) out of %d evaluated (mixed batch — persisting the rest).",
            len(rejected_evaluations), len(evaluations),
        )
        for evaluation in rejected_evaluations:
            logger.info(
                "Rejected, not persisted: question_text=%r, overall_score=%.2f, answer_correctness_score=%.2f",
                evaluation.question.question_text,
                evaluation.result.overall_score,
                evaluation.result.answer_correctness_score,
            )

    kept_questions = [q for q in questions if id(q) in kept_question_ids]

    # LearningOutcomes: Pydantic -> ORM. The Pydantic LO_001-style `id` is NOT
    # passed through — the ORM's own uuid.uuid4 default generates the real id.
    orm_outcomes = [
        LearningOutcomeORM(
            text=lo.text,
            concept=lo.concept,
            source_evidence=lo.source_evidence,
            context_hash=context_hash,
        )
        for lo in learning_outcomes
    ]
    await save_outcomes(db, orm_outcomes)
    lo_pydantic_id_to_orm = {lo.id: orm for lo, orm in zip(learning_outcomes, orm_outcomes)}

    # Questions: only the kept (accepted/needs_review) ones.
    orm_questions = [
        QuestionsORM(
            question_text=q.question_text,
            question_type=q.question_type.value,
            choices=q.choices,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            difficulty=q.difficulty,
            estimated_time_minutes=q.estimated_time_minutes,
            related_LO_ids=q.related_LO_ids,
            source_evidence=q.source_evidence,
        )
        for q in kept_questions
    ]
    await save_questions(db, orm_questions)
    question_identity_to_orm = {id(q): orm for q, orm in zip(kept_questions, orm_questions)}

    # QuestionLOLink: only for kept questions.
    orm_links = []
    for resolved in resolved_links:
        if id(resolved.question) not in kept_question_ids:
            continue
        orm_question = question_identity_to_orm.get(id(resolved.question))
        orm_lo = lo_pydantic_id_to_orm.get(resolved.learning_outcome.id)
        if orm_question is None or orm_lo is None:
            logger.warning(
                "Skipping unresolvable question-LO link (question_text=%r, lo_id=%r) — "
                "no matching saved ORM object found.",
                resolved.question.question_text, resolved.learning_outcome.id,
            )
            continue
        orm_links.append(
            QuestionLOLinkORM(
                question_id=orm_question.id,
                lo_id=orm_lo.id,
                confidence=resolved.link.confidence,
                reason=resolved.link.reason,
            )
        )
    await save_links(db, orm_links)

    # EvaluationResult: only for kept questions.
    orm_evaluations = []
    for evaluation in evaluations:
        if id(evaluation.question) not in kept_question_ids:
            continue
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

    # ── Auto-index kept questions into ChromaDB Vector Store ──
    if orm_questions:
        try:
            from services.embedding_service import embed_batch
            from services.vector_store import VectorStoreService

            q_texts = [q.question_text for q in orm_questions]
            embeddings = await embed_batch(q_texts)

            vector_ids = [str(q.id) for q in orm_questions]
            metadatas = [
                {
                    "question_text": q.question_text,
                    "difficulty": q.difficulty,
                    "question_type": q.question_type,
                    "lo_ids": [str(link.lo_id) for link in orm_links if link.question_id == q.id],
                }
                for q in orm_questions
            ]

            vector_store = VectorStoreService()
            vector_store.upsert_questions(ids=vector_ids, embeddings=embeddings, metadatas=metadatas)
            logger.info("Indexed %d questions into ChromaDB vector store.", len(orm_questions))
        except Exception as vec_exc:
            logger.warning("Failed to auto-index questions into ChromaDB: %s", vec_exc)

    status_breakdown = {"accepted": 0, "needs_review": 0, "rejected": 0}
    for evaluation in evaluations:
        status_breakdown[evaluation.result.status.value] += 1

    return {
        "persisted_learning_outcomes": len(orm_outcomes),
        "persisted_questions": len(orm_questions),
        "persisted_links": len(orm_links),
        "persisted_evaluations": len(orm_evaluations),
        "discarded_count": len(rejected_evaluations),
        "status_breakdown": status_breakdown,
    }


async def log_and_discard_node(state: GraphState) -> dict:
    """Every question in this batch was rejected — log why, touch the DB not at all."""
    evaluations = state["evaluations"]
    logger.info(
        "All %d question(s) in this batch were rejected — discarding entire batch, no DB writes.",
        len(evaluations),
    )
    for evaluation in evaluations:
        logger.info(
            "Rejected: question_text=%r, overall_score=%.2f, answer_correctness_score=%.2f",
            evaluation.question.question_text,
            evaluation.result.overall_score,
            evaluation.result.answer_correctness_score,
        )
    return {
        "persisted_learning_outcomes": 0,
        "persisted_questions": 0,
        "persisted_links": 0,
        "persisted_evaluations": 0,
        "discarded_count": len(evaluations),
        "status_breakdown": {"accepted": 0, "needs_review": 0, "rejected": len(evaluations)},
    }


_graph = StateGraph(GraphState)
_graph.add_node("parse", parse_node)
_graph.add_node("extract_outcomes", extract_outcomes_node)
_graph.add_node("generate_questions", generate_questions_node)
_graph.add_node("link_outcomes", link_outcomes_node)
_graph.add_node("evaluate", evaluate_node)
_graph.add_node("store", store_node)
_graph.add_node("log_and_discard", log_and_discard_node)

_graph.set_entry_point("parse")
_graph.add_edge("parse", "extract_outcomes")
_graph.add_edge("extract_outcomes", "generate_questions")
_graph.add_edge("generate_questions", "link_outcomes")
_graph.add_edge("link_outcomes", "evaluate")
_graph.add_conditional_edges("evaluate", route_after_evaluate, {"store": "store", "discard": "log_and_discard"})
_graph.add_edge("store", END)
_graph.add_edge("log_and_discard", END)

compiled_graph = _graph.compile()


async def run_pipeline(context: EducationalContext, db: AsyncSession) -> GraphState:
    """Run the full pipeline for one educational context, persisting only
    accepted/needs_review questions, and return the final state.

    This is the single entry point `routes/dataset.py`'s `POST /dataset/generate`
    calls. Persistence now happens INSIDE the graph (`store_node`/
    `log_and_discard_node`), not in the route — the route just reads
    `persisted_*`/`discarded_count`/`status_breakdown` off the returned state.

    Args:
        context: The educational context (passage + question_config +
            difficulty_distribution) to build a question set from.
        db: The request's DB session (threaded through graph state so
            store_node can use it — see GraphState's docstring).

    Returns:
        The final `GraphState`.

    Raises:
        RuntimeError: wrapping whichever AI-pipeline stage failed (see each
            node's docstring) — chained via `from exc`.
    """
    initial_state: GraphState = {
        "context": context,
        "db": db,
        "context_hash": "",
        "learning_outcomes": [],
        "questions": [],
        "resolved_links": [],
        "evaluations": [],
        "persisted_learning_outcomes": 0,
        "persisted_questions": 0,
        "persisted_links": 0,
        "persisted_evaluations": 0,
        "discarded_count": 0,
        "status_breakdown": {"accepted": 0, "needs_review": 0, "rejected": 0},
    }
    final_state = await compiled_graph.ainvoke(initial_state)
    logger.info(
        "Pipeline complete for context (subject=%s): %d LOs, %d questions generated, "
        "%d persisted / %d discarded, status_breakdown=%s",
        context.subject,
        len(final_state["learning_outcomes"]),
        len(final_state["questions"]),
        final_state["persisted_questions"],
        final_state["discarded_count"],
        final_state["status_breakdown"],
    )
    return final_state
