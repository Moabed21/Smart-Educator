"""LLM-as-a-judge evaluation of generated questions against their claimed LOs.

This is a deliberately SEPARATE Gemini pass from question generation
(question_generator.py) — the model that wrote a question must not be the
same call that grades it, or it will be biased toward approving its own
output. All questions for one context are judged together in a SINGLE
batched Gemini call (not one call per question): this keeps quota/cost/
latency down and is exactly as valid for a critical-judge pass, since each
question is still scored independently within the prompt.

`overall_score` and `status` are computed HERE in Python from the raw
per-criterion scores Gemini returns — not asked of Gemini directly. An LLM
doing its own threshold/arithmetic judgment on top of its own scores is an
unnecessary and unreliable extra inference step; a fixed, auditable formula
is more trustworthy and independently testable.
"""
import logging
from dataclasses import dataclass

from routes.schemes.evaluationResult import EvaluationResult, EvaluationStatus
from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questions import Question, QuestionType
from services.gemini_client import generate_structured_output
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger("server.evaluator")

# overall_score = simple (unweighted) average of the applicable criterion
# scores. The PRD does not specify per-criterion weights, so equal weighting
# is used here as a documented assumption — easy to swap for a weighted sum
# later without touching the rest of the pipeline. "Applicable" means: all 7
# always-required scores, plus choices_validity_score only when the question
# is MCQ (it's None/not applicable otherwise, so it's excluded from the
# average rather than penalizing non-MCQ questions for a criterion that
# doesn't apply to them).
_ALWAYS_ON_SCORE_FIELDS = (
    "context_grounding_score",
    "clarity_score",
    "answer_correctness_score",
    "explanation_correctness_score",
    "learning_outcome_alignment_score",
    "difficulty_score",
    "question_type_validity_score",
)

# Status thresholds as specified in team_strategy.md's P2 evaluator spec
# (not pinned in the PRD itself, but already fixed by the team plan, so used
# as-is rather than re-assumed): accepted >= 0.75, needs_review 0.5-0.74,
# rejected < 0.5.
_ACCEPTED_THRESHOLD = 0.75
_NEEDS_REVIEW_THRESHOLD = 0.5

# Hard override (explicit design decision, NOT specified in the PRD): a
# factually wrong correct_answer must never be accepted or merely flagged for
# review, no matter how well-written the rest of the question is. Equal-
# weight averaging alone lets a wrong answer_correctness_score get diluted by
# 6-7 other passing criteria and land in "needs_review" instead of
# "rejected" — verified empirically: a deliberately corrupted MCQ (wrong
# correct_answer, everything else fine) averaged to overall_score=0.625
# ("needs_review") before this override existed. So: if
# answer_correctness_score falls below this threshold, status is forced to
# REJECTED regardless of what the averaged overall_score says. overall_score
# itself is left untouched (still the plain average) — only status is
# overridden — so the numeric score keeps reflecting the real per-criterion
# breakdown for anyone reviewing it later.
_ANSWER_CORRECTNESS_REJECT_THRESHOLD = 0.5


class _CriteriaScores(BaseModel):
    """Gemini-facing wire schema — just the 8 raw judged criteria, no
    `overall_score`/`status` (those are computed locally, see module
    docstring) and no `question_id` (paired positionally, see
    `evaluate_questions`)."""

    context_grounding_score: float
    clarity_score: float
    answer_correctness_score: float
    explanation_correctness_score: float
    learning_outcome_alignment_score: float
    difficulty_score: float
    question_type_validity_score: float
    choices_validity_score: Optional[float] = None  # MCQ only


@dataclass
class ResolvedEvaluation:
    """An `EvaluationResult` paired with the question it judges.

    `EvaluationResult` itself has no `question_id` field (a known schema
    gap, not fixed here — same situation as `QuestionL0Link` in
    lo_linker.py). This dataclass carries the full `Question` object
    alongside the result so the caller can resolve the real DB id once the
    question is saved.
    """

    question: Question
    result: EvaluationResult


_PROMPT_TEMPLATE = """You are an impartial, critical exam-quality judge. You did NOT write any of the questions below — you are reviewing someone else's work and must be strict, not lenient.

For EACH question listed below, score it on these 8 criteria, each a float from 0.0 (completely fails this criterion) to 1.0 (fully satisfies it):

1. context_grounding_score — Is the question genuinely grounded in its `source_evidence` quote? (Not invented or unrelated to it.)
2. clarity_score — Is the question text clear, unambiguous, and well-formed?
3. answer_correctness_score — Is `correct_answer` actually correct given `source_evidence`?
4. explanation_correctness_score — Is `explanation` factually accurate and does it correctly justify `correct_answer`?
5. learning_outcome_alignment_score — Does the question TRULY test the learning outcome(s) listed for it (not just superficially mention related words)? If no valid learning outcome context is provided for a question below, score this 0.0.
6. difficulty_score — Is the stated `difficulty` label ("easy"/"medium"/"hard") a reasonable, honest assessment of how hard this question actually is?
7. question_type_validity_score — Is the question well-formed for its stated `question_type`? (e.g. an MCQ needs a genuine single correct choice; a true/false needs a clear factual statement; a short-answer needs a question that expects a brief factual answer.)
8. choices_validity_score — MCQ ONLY: are the 4 `choices` valid (no duplicates, all plausible, exactly one matches `correct_answer`)? Set this to null for true_false and short_answer questions — it does not apply to them.

Respond with EXACTLY {question_count} evaluation objects, in the EXACT SAME ORDER as the questions are listed below (question 1 first, question 2 second, etc.) — never skip, merge, reorder, or add extra objects. One evaluation object per question, no exceptions.

Questions to judge:

{question_blocks}
"""


def _format_question_block(
    index: int, question: Question, matched_los: list[LearningOutcome]
) -> str:
    """Render one question + its resolved LO context as a prompt block."""
    if matched_los:
        lo_context = "\n".join(f"    - {lo.id}: {lo.concept} — {lo.text}" for lo in matched_los)
    else:
        lo_context = "    (NONE — this question references no valid learning outcome; score learning_outcome_alignment_score as 0.0)"

    return (
        f"Question {index}:\n"
        f"  question_type: {question.question_type.value}\n"
        f"  question_text: {question.question_text}\n"
        f"  choices: {question.choices!r}\n"
        f"  correct_answer: {question.correct_answer}\n"
        f"  explanation: {question.explanation}\n"
        f"  difficulty: {question.difficulty}\n"
        f"  source_evidence: {question.source_evidence}\n"
        f"  claimed learning outcome(s):\n{lo_context}\n"
    )


def _compute_overall_score(scores: _CriteriaScores, is_mcq: bool) -> float:
    """Simple average of all always-applicable scores, plus
    choices_validity_score when the question is MCQ. See module docstring
    for why equal weighting was chosen (PRD doesn't specify weights)."""
    values = [getattr(scores, field) for field in _ALWAYS_ON_SCORE_FIELDS]
    if is_mcq and scores.choices_validity_score is not None:
        values.append(scores.choices_validity_score)
    return sum(values) / len(values)


def _compute_status(overall_score: float, answer_correctness_score: float) -> EvaluationStatus:
    """Threshold as specified in team_strategy.md: >=0.75 accepted,
    0.5-0.74 needs_review, <0.5 rejected — EXCEPT a hard override: if
    answer_correctness_score is below `_ANSWER_CORRECTNESS_REJECT_THRESHOLD`,
    status is forced to REJECTED regardless of overall_score. See the module-
    level comment above `_ANSWER_CORRECTNESS_REJECT_THRESHOLD` for why."""
    if answer_correctness_score < _ANSWER_CORRECTNESS_REJECT_THRESHOLD:
        return EvaluationStatus.REJECTED
    if overall_score >= _ACCEPTED_THRESHOLD:
        return EvaluationStatus.ACCEPTED
    if overall_score >= _NEEDS_REVIEW_THRESHOLD:
        return EvaluationStatus.NEEDS_REVIEW
    return EvaluationStatus.REJECTED


async def evaluate_questions(
    questions: list[Question], learning_outcomes: list[LearningOutcome]
) -> list[ResolvedEvaluation]:
    """Judge each question against its claimed LO(s) in a single batched Gemini call.

    Builds one prompt listing every question (with its resolved LO context,
    looked up from `learning_outcomes` by the ids in
    `question.related_LO_ids` — ids that don't resolve are simply omitted
    from that question's LO context, mirroring lo_linker's skip behavior, no
    crash) and asks Gemini to score all 8 criteria for every question in one
    pass, in the same order as given. `overall_score` and `status` are then
    computed locally (see module docstring) rather than asked of Gemini.

    Args:
        questions: Questions from `question_generator.generate_questions`.
        learning_outcomes: The real LOs from
            `lo_extraction.extract_learning_outcomes` for the same context.

    Returns:
        One `ResolvedEvaluation` per input question, in the same order.

    Raises:
        Whatever `generate_structured_output` raises on a non-retryable
        Gemini error, or a `pydantic.ValidationError` if Gemini's output
        still didn't match the schema after all retries.
        ValueError: if Gemini returned a different number of evaluation
            objects than questions given — positional pairing would be
            unreliable, so this is raised rather than silently mispairing.
    """
    lo_by_id = {lo.id: lo for lo in learning_outcomes}

    question_blocks = "\n".join(
        _format_question_block(
            i, question, [lo_by_id[lo_id] for lo_id in question.related_LO_ids if lo_id in lo_by_id]
        )
        for i, question in enumerate(questions, start=1)
    )
    prompt = _PROMPT_TEMPLATE.format(question_count=len(questions), question_blocks=question_blocks)

    all_scores = await generate_structured_output(prompt, list[_CriteriaScores])

    if len(all_scores) != len(questions):
        raise ValueError(
            f"Gemini returned {len(all_scores)} evaluations for {len(questions)} questions — "
            "counts must match for positional pairing to be reliable."
        )

    evaluations: list[ResolvedEvaluation] = []
    for question, scores in zip(questions, all_scores):
        is_mcq = question.question_type == QuestionType.MCQ
        overall_score = _compute_overall_score(scores, is_mcq)
        status = _compute_status(overall_score, scores.answer_correctness_score)
        result = EvaluationResult(
            context_grounding_score=scores.context_grounding_score,
            clarity_score=scores.clarity_score,
            answer_correctness_score=scores.answer_correctness_score,
            explanation_correctness_score=scores.explanation_correctness_score,
            learning_outcome_alignment_score=scores.learning_outcome_alignment_score,
            difficulty_score=scores.difficulty_score,
            question_type_validity_score=scores.question_type_validity_score,
            choices_validity_score=scores.choices_validity_score if is_mcq else None,
            overall_score=overall_score,
            status=status,
        )
        evaluations.append(ResolvedEvaluation(question=question, result=result))

    logger.info(
        "Evaluated %d questions: %d accepted, %d needs_review, %d rejected",
        len(evaluations),
        sum(1 for e in evaluations if e.result.status == EvaluationStatus.ACCEPTED),
        sum(1 for e in evaluations if e.result.status == EvaluationStatus.NEEDS_REVIEW),
        sum(1 for e in evaluations if e.result.status == EvaluationStatus.REJECTED),
    )
    return evaluations
