"""Learning-outcome extraction from an EducationalContext passage via Gemini."""
import logging

from routes.schemes.educationalContext import EducationalContext
from routes.schemes.learningOutcome import LearningOutcome
from services.gemini_client import generate_structured_output

logger = logging.getLogger("server.lo_extraction")

_PROMPT_TEMPLATE = """You are an expert curriculum designer extracting learning outcomes (LOs) from an educational passage.

Subject: {subject}
Grade level: {grade_level}

Passage:
\"\"\"
{passage}
\"\"\"

Extract a list of learning outcomes from the passage above.

Respond ENTIRELY IN ARABIC for every text field (text, concept, source_evidence).
Do not use English in any field value — the students and lesson are Arabic-speaking.

Strict rules:
1. Each learning outcome must represent exactly ONE clear, single skill or concept — do not combine multiple skills into one LO.
2. Assign sequential IDs starting at "LO_001", then "LO_002", "LO_003", and so on, in the order the outcomes appear.
3. `source_evidence` must be an EXACT quote copied verbatim from the passage above — never a summary, paraphrase, or translation of it. It must be text that literally appears in the passage.
4. Do not fabricate, infer, or add any information that is not explicitly present in the passage. If the passage does not support a claim, do not generate an LO for it.
5. Every single LO record MUST include ALL FOUR fields with no exceptions: `id`, `text`, `concept`, `source_evidence`. A record missing any one of these four fields is invalid — never omit a field, never leave one blank.

Return only the structured list of learning outcomes matching the required schema."""


async def extract_learning_outcomes(context: EducationalContext) -> list[LearningOutcome]:
    """Extract learning outcomes from an EducationalContext's passage using Gemini.

    Builds a prompt (in English) that instructs Gemini to answer in Arabic for
    all text fields, then calls `generate_structured_output` with the
    `LearningOutcome` schema — validation (and retry-on-invalid-output) is
    handled inside `generate_structured_output` itself.

    Args:
        context: The educational context containing the source passage.

    Returns:
        A list of `LearningOutcome` Pydantic objects, each with a sequential
        `LO_001`-style id, and Arabic `text`/`concept`/`source_evidence`.

    Raises:
        Whatever `generate_structured_output` raises on a non-retryable Gemini
        error, or a `pydantic.ValidationError` if Gemini's output still didn't
        match the schema after all retry attempts were exhausted.
    """
    prompt = _PROMPT_TEMPLATE.format(
        subject=context.subject,
        grade_level=context.grade_level,
        passage=context.passage,
    )

    outcomes = await generate_structured_output(prompt, list[LearningOutcome])
    logger.info("Extracted %d learning outcomes from context (subject=%s)", len(outcomes), context.subject)
    return outcomes
