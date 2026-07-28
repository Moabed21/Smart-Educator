"""Question generation from an EducationalContext + its extracted LearningOutcomes via Gemini."""
import logging

from routes.schemes.educationalContext import EducationalContext
from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questions import Question
from services.gemini_client import generate_structured_output

logger = logging.getLogger("server.question_generator")

_PROMPT_TEMPLATE = """You are an expert assessment designer generating exam questions from an educational passage, targeting a given set of learning outcomes (LOs).

Subject: {subject}
Grade level: {grade_level}

Passage:
\"\"\"
{passage}
\"\"\"

Learning outcomes already extracted for this passage (use ONLY these — never invent new LO ids):
{lo_list}

Generate EXACTLY:
- {mcq_count} multiple-choice questions (type "mcq")
- {true_false_count} true/false questions (type "true_false")
- {short_answer_count} short-answer questions (type "short_answer")

Distribute difficulty roughly according to this target mix (fractions of the total question count):
- easy: {difficulty_easy}
- medium: {difficulty_medium}
- hard: {difficulty_hard}

Respond ENTIRELY IN ARABIC for every free-text field (question_text, choices, correct_answer, explanation) — the students are Arabic-speaking. The only fields that must stay in their exact literal form (not translated) are: question_type ("mcq" / "true_false" / "short_answer") and difficulty ("easy" / "medium" / "hard").

Strict rules:
1. Every question must be linked, via `related_LO_ids`, to at least one of the exact LO ids listed above (e.g. "LO_001"). Never invent an LO id that isn't in the list above.
2. MCQ questions must have EXACTLY 4 entries in `choices`: one correct answer and three plausible-but-wrong distractors. `correct_answer` must exactly match one of the 4 choices.
3. True/False and short-answer questions must set `choices` to null — never a populated list, since choices do not apply to those question types.
4. `source_evidence` must be an EXACT quote copied verbatim from the passage above — never a summary, paraphrase, or translation of it.
5. Do not fabricate, infer, or add any information that is not explicitly present in the passage.
6. Distribute the questions across the provided LOs as evenly as reasonable — do not generate all questions for only one LO when multiple LOs are available.
7. Every single question record MUST include ALL of these fields with no exceptions: `question_text`, `question_type`, `correct_answer`, `explanation`, `difficulty`, `estimated_time_minutes`, `related_LO_ids`, `source_evidence` (plus `choices` for MCQ only). Never omit a required field.

Return only the structured list of questions matching the required schema."""


def _format_lo_list(learning_outcomes: list[LearningOutcome]) -> str:
    """Render LOs as a compact numbered reference list for the prompt."""
    return "\n".join(
        f"- {lo.id}: {lo.concept} — {lo.text}" for lo in learning_outcomes
    )


async def generate_questions(
    context: EducationalContext, learning_outcomes: list[LearningOutcome]
) -> list[Question]:
    """Generate exam questions from a passage, targeting already-extracted LOs, via Gemini.

    Builds a prompt (in English) that instructs Gemini to answer in Arabic for
    all free-text fields, respects the exact question counts from
    `context.question_config` and the approximate `difficulty_distribution`,
    and requires every question to reference one of the given LO ids. Calls
    `generate_structured_output` with the `Question` schema — validation and
    retry-on-invalid-output are handled inside `generate_structured_output`
    itself.

    Args:
        context: The educational context (passage + question_config +
            difficulty_distribution) the questions are generated from.
        learning_outcomes: The LOs already extracted for this same passage
            (from `lo_extraction.extract_learning_outcomes`) — questions must
            link back to these exact ids.

    Returns:
        A list of `Question` Pydantic objects matching
        `context.question_config`'s exact mcq/true_false/short_answer counts.

    Raises:
        Whatever `generate_structured_output` raises on a non-retryable Gemini
        error, or a `pydantic.ValidationError` if Gemini's output still didn't
        match the schema after all retry attempts were exhausted.
    """
    prompt = _PROMPT_TEMPLATE.format(
        subject=context.subject,
        grade_level=context.grade_level,
        passage=context.passage,
        lo_list=_format_lo_list(learning_outcomes),
        mcq_count=context.question_config.mcq_count,
        true_false_count=context.question_config.true_false_count,
        short_answer_count=context.question_config.short_answer_count,
        difficulty_easy=context.difficulty_distribution.easy,
        difficulty_medium=context.difficulty_distribution.medium,
        difficulty_hard=context.difficulty_distribution.hard,
    )

    questions = await generate_structured_output(prompt, list[Question])
    logger.info(
        "Generated %d questions from context (subject=%s)", len(questions), context.subject
    )
    return questions
