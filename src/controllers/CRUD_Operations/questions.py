from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.questions import Questions


async def save_questions(db: AsyncSession, questions: list[Questions]) -> None:
    """
    Bulk insert questions after Gemini generates them.
    Each question should already have all fields populated by the AI pipeline.
    """
    db.add_all(questions)
    await db.commit()


async def get_question_by_id(db: AsyncSession, question_id) -> Questions | None:
    """Fetch a single question by its UUID — used by evaluation and linking."""
    result = await db.execute(
        select(Questions).where(Questions.id == question_id)
    )
    return result.scalar_one_or_none()


async def get_all_questions(db: AsyncSession) -> list[Questions]:
    """Fetch all questions — used by embedding pipeline and dataset export."""
    result = await db.execute(select(Questions))
    return result.scalars().all()


async def get_accepted_questions(db: AsyncSession) -> list[Questions]:
    """
    Fetch only questions with accepted/needs_review evaluations.
    Used by:
    - GET /dataset/export (only clean data)
    - Embedding pipeline (only embed approved questions)

    Joins with evaluation_results to filter by status.
    """
    from models.evaluationResult import EvaluationResult

    result = await db.execute(
        select(Questions)
        .join(EvaluationResult, EvaluationResult.question_id == Questions.id)
        .where(EvaluationResult.status.in_(["accepted", "needs_review"]))
    )
    return result.scalars().all()
