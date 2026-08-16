import asyncio
import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from crud.learning_outcomes import get_all_outcomes
from crud.question_lo_links import get_links_by_question
from crud.questions import get_accepted_questions
from helpers.db import get_db
from services.pair_generator import QuestionWithLO, export_pairs_jsonl, generate_pairs

training_pairs_router = APIRouter(
    prefix="/api/v1/training-pairs",
    tags=["training-pairs"]
)

@training_pairs_router.post("/build")
async def build_training_pairs(db: AsyncSession = Depends(get_db)):
    """Build positive, negative, and hard-negative training pairs from saved DB questions per PRD §8.7 & §9.

    Exports pairs to assets/training_pairs.jsonl and returns pair statistics.
    """
    accepted_questions = await get_accepted_questions(db)
    all_outcomes = {lo.id: lo for lo in await get_all_outcomes(db)}

    questions_with_lo: list[QuestionWithLO] = []

    for q in accepted_questions:
        links = await get_links_by_question(db, q.id)
        for link in links:
            lo = all_outcomes.get(link.lo_id)
            if lo:
                questions_with_lo.append(
                    QuestionWithLO(
                        question_id=str(q.id),
                        question_text=q.question_text,
                        lo_id=str(lo.id),
                        concept=lo.concept,
                    )
                )

    pairs = generate_pairs(questions_with_lo)

    pos_count = sum(1 for p in pairs if p.pair_type == "positive")
    neg_count = sum(1 for p in pairs if p.pair_type == "negative")
    hard_neg_count = sum(1 for p in pairs if p.pair_type == "hard_negative")

    if pairs:
        os.makedirs("assets", exist_ok=True)
        export_pairs_jsonl(pairs, "assets/training_pairs.jsonl")

    return {
        "total_pairs": len(pairs),
        "positive_pairs": pos_count,
        "negative_pairs": neg_count,
        "hard_negative_pairs": hard_neg_count,
        "export_path": "assets/training_pairs.jsonl" if pairs else None,
    }
