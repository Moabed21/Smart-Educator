"""Link generated Questions back to their claimed LearningOutcomes, in memory.

Gemini already claims a `related_LO_ids` list per question (see
question_generator.py). This module verifies those claims against the real
extracted LO list, scores each surviving link with embedding-based semantic
similarity (via Gemini Embeddings API), and attaches a human-readable Arabic
reason — before any DB save happens. It does NOT touch the database and does
not build the ORM `QuestionLOLink` rows (those need real question/LO UUIDs,
which only exist after `save_questions`/`save_outcomes` run).
"""
import logging
from dataclasses import dataclass
import numpy as np

from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questionL0Link import QuestionL0Link
from routes.schemes.questions import Question
from services.embedding_service import embed_batch

logger = logging.getLogger("server.lo_linker")


@dataclass
class ResolvedLink:
    """A `QuestionL0Link` paired with the actual question/LO it connects.

    `QuestionL0Link` itself only carries `confidence` + `reason` — it has no
    `question_id`/`lo_id` fields. This dataclass carries the full objects
    alongside the link so the caller can resolve real DB ids once both are saved.
    """

    question: Question
    learning_outcome: LearningOutcome
    link: QuestionL0Link


def _build_reason(concept: str, confidence: float) -> str:
    """Build an Arabic explanation for why a question was linked to an LO."""
    return (
        f"يرتبط هذا السؤال بمخرج التعلم لأنه يتناول مفهوم '{concept}' "
        f"الذي يمثل جوهر هذا المخرج، بدرجة تشابه دلالي بين نص السؤال "
        f"ونص المخرج تُقدَّر بـ {confidence:.2f}."
    )


def _cosine_similarity(vec_a: list[float] | np.ndarray, vec_b: list[float] | np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def link_questions_to_outcomes(
    questions: list[Question], learning_outcomes: list[LearningOutcome]
) -> list[ResolvedLink]:
    """Resolve each question's claimed `related_LO_ids` into scored links.

    For every (question, claimed LO id) pair: looks up the real
    `LearningOutcome` by id, skips any invalid id, and computes cosine similarity
    between question and LO embeddings using the high-dimensional Gemini
    embeddings API.

    Args:
        questions: Questions from `question_generator.generate_questions`,
            each with claimed `related_LO_ids`.
        learning_outcomes: The real LOs from
            `lo_extraction.extract_learning_outcomes` for the same context.

    Returns:
        One `ResolvedLink` per (question, LO id) pair that resolved to a
        real LO.
    """
    lo_by_id = {lo.id: lo for lo in learning_outcomes}

    pairs: list[tuple[Question, LearningOutcome]] = []
    for question in questions:
        for lo_id in question.related_LO_ids:
            lo = lo_by_id.get(lo_id)
            if lo is None:
                logger.warning(
                    "Question claims unknown LO id %r (not in extracted LO list) — "
                    "skipping this link. question_text=%r",
                    lo_id, question.question_text,
                )
                continue
            pairs.append((question, lo))

    if not pairs:
        logger.warning("No valid question-to-LO links resolved out of %d questions.", len(questions))
        return []

    # Extract all distinct texts to embed in a single batch
    question_texts = [q.question_text for q, _ in pairs]
    lo_texts = [lo.text for _, lo in pairs]

    # Combine into single embedding request for efficiency
    all_texts = question_texts + lo_texts
    all_embeddings = await embed_batch(all_texts)

    num_pairs = len(pairs)
    q_embeddings = all_embeddings[:num_pairs]
    lo_embeddings = all_embeddings[num_pairs:]

    links: list[ResolvedLink] = []
    for (question, lo), q_emb, lo_emb in zip(pairs, q_embeddings, lo_embeddings):
        raw_score = _cosine_similarity(q_emb, lo_emb)
        confidence = max(0.0, min(1.0, raw_score))
        reason = _build_reason(lo.concept, confidence)
        links.append(
            ResolvedLink(
                question=question,
                learning_outcome=lo,
                link=QuestionL0Link(confidence=confidence, reason=reason),
            )
        )

    logger.info("Resolved %d question-to-LO links out of %d questions.", len(links), len(questions))
    return links
