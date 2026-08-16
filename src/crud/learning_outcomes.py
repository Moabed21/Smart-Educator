from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.learningOutcome import LearningOutcome


async def save_outcomes(db: AsyncSession, outcomes: list[LearningOutcome]) -> None:
    """
    Insert a list of LearningOutcome objects into the DB.
    Called after Gemini extracts LOs from an educational context.
    """
    db.add_all(outcomes)
    await db.commit()


async def get_outcomes_by_hash(db: AsyncSession, context_hash: str) -> list[LearningOutcome]:
    """
    Fetch all LOs for a given context hash.
    Used to check if this context was already processed (idempotency).
    Returns empty list if no match → triggers fresh Gemini extraction.
    """
    result = await db.execute(
        select(LearningOutcome).where(LearningOutcome.context_hash == context_hash)
    )
    return result.scalars().all()


async def get_all_outcomes(db: AsyncSession) -> list[LearningOutcome]:
    """Fetch all learning outcomes — used by dataset export."""
    result = await db.execute(select(LearningOutcome))
    return result.scalars().all()
