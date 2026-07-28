"""Link generated Questions back to their claimed LearningOutcomes, in memory.

Gemini already claims a `related_LO_ids` list per question (see
question_generator.py). This module verifies those claims against the real
extracted LO list, scores each surviving link with embedding-based semantic
similarity, and attaches a human-readable Arabic reason — before any DB save
happens. It does NOT touch the database and does NOT build the ORM
`QuestionLOLink` rows (those need real question/LO UUIDs, which only exist
after `save_questions`/`save_outcomes` run).
"""
import asyncio
import logging
from dataclasses import dataclass

from sentence_transformers import SentenceTransformer

from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questionL0Link import QuestionL0Link
from routes.schemes.questions import Question

logger = logging.getLogger("server.lo_linker")

_EMBEDDING_MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazily load the sentence-transformers model once per process.

    First call downloads the model weights (~1GB) if not already cached
    locally — expect it to be noticeably slower than subsequent calls.
    """
    global _model
    if _model is None:
        logger.info("Loading sentence-transformers model %r ...", _EMBEDDING_MODEL_NAME)
        _model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
        logger.info("Model %r loaded.", _EMBEDDING_MODEL_NAME)
    return _model


@dataclass
class ResolvedLink:
    """A `QuestionL0Link` paired with the actual question/LO it connects.

    `QuestionL0Link` itself only carries `confidence` + `reason` — it has no
    `question_id`/`lo_id` fields (a known schema gap, not fixed here; see
    module docstring). This dataclass carries the full objects alongside the
    link so the caller can resolve real DB ids once both are saved.
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


async def link_questions_to_outcomes(
    questions: list[Question], learning_outcomes: list[LearningOutcome]
) -> list[ResolvedLink]:
    """Resolve each question's claimed `related_LO_ids` into scored links.

    For every (question, claimed LO id) pair: looks up the real
    `LearningOutcome` by id, skips (with a warning, no exception) any id
    Gemini invented that isn't in `learning_outcomes`, then scores the
    surviving pairs with cosine similarity between `question.question_text`
    and `learning_outcome.text` embeddings (`paraphrase-multilingual-mpnet-base-v2`,
    since the passage/questions are Arabic). All pairs are embedded in two
    batched `encode()` calls rather than one call per pair, and the
    (CPU-bound) model loading/encoding is run in a worker thread via
    `asyncio.to_thread` so it doesn't block the event loop.

    Args:
        questions: Questions from `question_generator.generate_questions`,
            each with Gemini's own claimed `related_LO_ids`.
        learning_outcomes: The real LOs from
            `lo_extraction.extract_learning_outcomes` for the same context —
            the source of truth `related_LO_ids` is checked against.

    Returns:
        One `ResolvedLink` per (question, LO id) pair that resolved to a
        real LO — invented/unknown ids are dropped, not raised as errors.
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

    def _encode_and_score() -> list[float]:
        model = _get_model()
        question_texts = [q.question_text for q, _ in pairs]
        lo_texts = [lo.text for _, lo in pairs]
        # normalize_embeddings=True makes the dot product equal cosine similarity
        question_embeddings = model.encode(question_texts, normalize_embeddings=True)
        lo_embeddings = model.encode(lo_texts, normalize_embeddings=True)
        return [float((q_emb * lo_emb).sum()) for q_emb, lo_emb in zip(question_embeddings, lo_embeddings)]

    raw_scores = await asyncio.to_thread(_encode_and_score)

    links: list[ResolvedLink] = []
    for (question, lo), raw_score in zip(pairs, raw_scores):
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
