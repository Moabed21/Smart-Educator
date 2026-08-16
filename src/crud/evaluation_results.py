from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.evaluationResult import EvaluationResult


async def save_evaluations(db: AsyncSession, evaluations: list[EvaluationResult]) -> None:
    """
    Bulk insert evaluation results after the LLM-as-Judge scores each question.
    Each evaluation has 8 criteria scores + overall_score + status.
    """
    db.add_all(evaluations)
    await db.commit()


async def get_evaluation_by_question(db: AsyncSession, question_id) -> EvaluationResult | None:
    """Fetch the evaluation for a specific question — used by export."""
    result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.question_id == question_id)
    )
    return result.scalar_one_or_none()


async def get_evaluations_by_status(db: AsyncSession, status: str) -> list[EvaluationResult]:
    """
    Fetch all evaluations with a given status.
    status is one of: "accepted", "rejected", "needs_review"
    Used by dataset export (accepted + needs_review only).
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
    """
    result = await db.execute(
        select(EvaluationResult.status, func.count(EvaluationResult.id))
        .group_by(EvaluationResult.status)
    )
    return {row[0]: row[1] for row in result.all()}
