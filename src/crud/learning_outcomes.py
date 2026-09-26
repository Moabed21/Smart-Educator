"""CRUD operations for the Learning Outcomes (LO) table.

Manages persistence and lookup for granular educational objectives extracted
from curriculum passages by Google Gemini.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.learningOutcome import LearningOutcome


async def save_outcomes(db: AsyncSession, outcomes: list[LearningOutcome]) -> None:
    """
    Insert a list of LearningOutcome objects into the DB.
    Called after Gemini extracts LOs from an educational context.
    
    EXPLANATION:
    - db.add_all(outcomes): Stages all LearningOutcome instances into the session.
    - await db.commit(): Asynchronously persists all staged LO rows to PostgreSQL.
    """
    db.add_all(outcomes)
    await db.commit()


async def get_all_outcomes(db: AsyncSession) -> list[LearningOutcome]:
    """
    Fetch all learning outcomes — used by dataset export and training pair building.
    
    EXPLANATION:
    - Materializes all LO records to map LO IDs to their textual definitions in memory.
    """
    result = await db.execute(select(LearningOutcome))
    return result.scalars().all()

