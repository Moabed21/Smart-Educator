from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.questions import Questions


async def save_questions(db: AsyncSession, questions: list[Questions]) -> None:
    """
    Bulk insert questions after Gemini generates them.
    Each question should already have all fields populated by the AI pipeline.
    """
    if not questions:
        return
    db.add_all(questions)
    await db.flush()
    # flush prevents closing the transaction if any error occurs and make a rollback
    # commit closes the transaction permanently.
    await db.commit()

async def get_question_by_id(db: AsyncSession, question_id) -> Questions | None:
    """Fetch a single question by its UUID — used by evaluation and linking."""
    result = await db.execute(
        select(Questions).where(Questions.id == question_id)
    )
    # scalar_one_or_none means return single unique object, if not exists return none
    return result.scalar_one_or_none()


async def get_all_questions(db: AsyncSession) -> list[Questions]:
    """Fetch all questions — used by embedding pipeline and dataset export."""
    result = await db.execute(select(Questions))
    # scalar.all means return list of python objects, used when querying multiple items
    # items like here
    return result.scalars().all()


async def get_accepted_questions(db: AsyncSession) -> list[Questions]:
    """
    Fetch only questions with accepted/needs_review evaluations.
    Used by:
    - GET /dataset/export (only clean data)
    - Embedding pipeline (only embed approved questions)

    Joins with evaluation_results to filter by status and ensures distinct questions.
    """
    from models.evaluationResult import EvaluationResult

    result = await db.execute(
        select(Questions)
        .join(EvaluationResult, EvaluationResult.question_id == Questions.id)
        .where(EvaluationResult.status.in_(["accepted", "needs_review"]))
        .group_by(Questions.id)
    )
    return result.scalars().all()


async def get_questions_by_ids(db: AsyncSession, question_ids: list) -> list[Questions]:
    # Solving the N+1 query latency problem
    if not question_ids:
        return []
    result = await db.execute(
        select(Questions).where(Questions.id.in_(question_ids))
    )
    return result.scalars().all()

