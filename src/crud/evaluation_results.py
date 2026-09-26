"""CRUD operations for the Evaluation Results table.

Persists and queries LLM-as-Judge evaluation scores (8 criteria + overall score)
and validation statuses (accepted, needs_review, rejected).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.evaluationResult import EvaluationResult


async def save_evaluations(db: AsyncSession, evaluations: list[EvaluationResult]) -> None:
    """
    Bulk insert evaluation results after the LLM-as-Judge scores each question.
    Each evaluation has 8 criteria scores + overall_score + status.
    
    EXPLANATION:
    - Stages and commits all evaluation metrics generated during Node 5 of the
      LangGraph pipeline into PostgreSQL.
    """
    db.add_all(evaluations)
    await db.commit()


async def get_evaluation_by_question(db: AsyncSession, question_id) -> EvaluationResult | None:
    """
    Fetch the evaluation for a specific question — used by export.
    
    EXPLANATION:
    - scalar_one_or_none(): Returns the unique EvaluationResult object for the question,
      or None if the question has not yet been evaluated.
    """
    result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.question_id == question_id)
    )
    return result.scalar_one_or_none()


async def get_evaluations_by_status(db: AsyncSession, status: str) -> list[EvaluationResult]:
    """
    Fetch all evaluations with a given status.
    status is one of: "accepted", "rejected", "needs_review"
    Used by dataset export (accepted + needs_review only).
    
    EXPLANATION:
    - Allows dataset export and dashboards to filter approved vs rejected questions.
    """
    result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.status == status)
    )
    return result.scalars().all()


async def get_status_counts(db: AsyncSession) -> dict:
    """
    Returns a count of evaluations per status.
    Example: {"accepted": 42, "rejected": 8, "needs_review": 5}
    Used by health checks and dashboard reporting.
    
    EXPLANATION:
    - SQL Group-By Aggregation: Generates `SELECT status, COUNT(id) FROM evaluation_results GROUP BY status`
      executed on the database server to minimize network transfer.
    - result.all() returns list of (status, count) tuples converted to a dictionary.
    """
    result = await db.execute(
        select(EvaluationResult.status, func.count(EvaluationResult.id))
        .group_by(EvaluationResult.status)
    )
    return {row[0]: row[1] for row in result.all()}

