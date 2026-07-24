from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.questionL0Link import QuestionLOLink


async def save_links(db: AsyncSession, links: list[QuestionLOLink]) -> None:
    """
    Bulk insert question-to-LO links after the linker assigns LOs to questions.
    Each link has: question_id, lo_id, confidence, reason.
    """
    db.add_all(links)
    await db.commit()


async def get_links_by_question(db: AsyncSession, question_id) -> list[QuestionLOLink]:
    """Fetch all LO links for a specific question — used by export and recommendation."""
    result = await db.execute(
        select(QuestionLOLink).where(QuestionLOLink.question_id == question_id)
    )
    return result.scalars().all()


async def get_links_by_lo(db: AsyncSession, lo_id) -> list[QuestionLOLink]:
    """
    Fetch all questions linked to a specific LO.
    Used by training pair generation:
    - Questions sharing the same LO → positive pairs
    - Questions with different LOs → negative pairs
    """
    result = await db.execute(
        select(QuestionLOLink).where(QuestionLOLink.lo_id == lo_id)
    )
    return result.scalars().all()
