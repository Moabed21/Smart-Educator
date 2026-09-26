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


async def get_outcomes_by_hash(db: AsyncSession, context_hash: str) -> list[LearningOutcome]:
    """
    Fetch all LOs for a given context hash.
    Used to check if this context was already processed (idempotency).
    Returns empty list if no match → triggers fresh Gemini extraction.
    
    EXPLANATION:
    - Idempotency & Deduplication: `context_hash` is a SHA-256 fingerprint of
      (passage + question_config). By checking the database before invoking Gemini,
      we avoid duplicate AI calls and prevent redundant rows in the database.
    - result.scalars().all(): Unpacks row objects into a Python list[LearningOutcome].
    """
    result = await db.execute(
        select(LearningOutcome).where(LearningOutcome.context_hash == context_hash)
    )
    return result.scalars().all()


async def get_all_outcomes(db: AsyncSession) -> list[LearningOutcome]:
    """
    Fetch all learning outcomes — used by dataset export and training pair building.
    
    EXPLANATION:
    - Materializes all LO records to map LO IDs to their textual definitions in memory.
    """
    result = await db.execute(select(LearningOutcome))
    return result.scalars().all()

