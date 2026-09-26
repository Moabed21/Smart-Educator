"""CRUD operations for the Evaluation Results table.

Persists and queries LLM-as-Judge evaluation scores (8 criteria + overall score)
and validation statuses (accepted, needs_review, rejected).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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

