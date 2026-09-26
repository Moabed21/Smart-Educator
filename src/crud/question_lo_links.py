"""CRUD operations for the Question-to-Learning-Outcome Link table.

Manages the association table (QuestionLOLink) that records semantic mapping,
similarity confidence scores, and reasoning between generated questions and target LOs.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.questionL0Link import QuestionLOLink


async def save_links(db: AsyncSession, links: list[QuestionLOLink]) -> None:
    """
    Bulk insert question-to-LO links after the linker assigns LOs to questions.
    Each link has: question_id, lo_id, confidence, reason.
    
    EXPLANATION:
    - Many-to-Many Linking: Rather than a rigid 1-to-1 relationship, a question can
      align with multiple LOs. The linker service computes cosine similarity
      between question and LO embeddings and persists records with confidence scores.
    """
    db.add_all(links)
    await db.commit()


async def get_links_by_question(db: AsyncSession, question_id) -> list[QuestionLOLink]:
    """
    Fetch all LO links for a specific question — used by export and recommendation.
    
    EXPLANATION:
    - Allows the exporter and quiz engine to look up which concepts a question tests.
    """
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
    
    EXPLANATION:
    - Crucial for Contrastive Fine-Tuning: In fine_tune.py / pair_generator.py,
      items addressing the identical LO are treated as semantically equivalent
      (positive pairs), helping fine-tune embedding models for curriculum retrieval.
    """
    result = await db.execute(
        select(QuestionLOLink).where(QuestionLOLink.lo_id == lo_id)
    )
    return result.scalars().all()

