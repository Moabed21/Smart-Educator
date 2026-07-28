"""Async wrapper around google-genai for structured (JSON) output.

Uses `google.genai` (Google's current SDK) rather than the deprecated
`google-generativeai`: the old SDK's automatic Pydantic-model-to-Schema
converter is buggy for models with several fields/an enum/a list — it either
raises on fields with a default value, or silently drops properties past a
certain point, causing Gemini to dump the missing fields as raw text into the
last known field instead of separate JSON keys. `google-genai` handles
Pydantic response_schema correctly.
"""
import asyncio
import logging

from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import TypeAdapter, ValidationError

from helpers.config import get_settings

logger = logging.getLogger("server.gemini")

_MODEL_NAME = "gemini-flash-lite-latest"
_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = (2, 4, 8)

# HTTP status codes that are transient — worth retrying (rate limit, server-side hiccup).
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}

# HTTP status codes that will never succeed on retry — fail fast instead of wasting attempts.
_NON_RETRYABLE_HTTP_CODES = {400, 401, 403, 404}

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazily create the genai.Client, configured with GEMINI_API_KEY, once per process."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().GEMINI_API_KEY)
    return _client


async def generate_structured_output(
    prompt: str, response_schema: type, max_output_tokens: int = 16384
):
    """Call Gemini with structured-output mode and return validated objects.

    Args:
        prompt: Full instruction + content prompt sent to the model.
        response_schema: A Pydantic model (or list[PydanticModel]) describing the
            exact JSON shape Gemini must return. Passed straight to the SDK's
            `response_schema` config, and reused here to validate the response.
        max_output_tokens: Ceiling on generated tokens. Structured JSON output
            for a list of records can be long; too low a value truncates the
            JSON mid-string and breaks parsing. Raise this for large passages
            or high LO/question counts.

    Returns:
        The response parsed and validated into `response_schema` (e.g. a
        `list[LearningOutcome]`) — already real Pydantic objects, no manual
        `json.loads` needed by the caller.

    Raises:
        APIError: with a 4xx code in `_NON_RETRYABLE_HTTP_CODES` (bad request,
            bad/missing API key, no access) — retrying will not help, raised
            immediately.
        ValueError: if Gemini's response was cut off by the token limit before
            the JSON was complete — retrying with the same limit would just
            truncate again, so this is raised immediately instead of retried.
        pydantic.ValidationError: if Gemini's JSON still doesn't match
            `response_schema` (e.g. a missing required field) after
            `_MAX_ATTEMPTS` retries — treated as retryable since this is
            usually a one-off generation slip, not a persistent failure.
        APIError: with a retryable code (429/5xx), re-raised after
            `_MAX_ATTEMPTS` exhausted retries.
    """
    client = _get_client()

    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            response = await client.aio.models.generate_content(
                model=_MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    max_output_tokens=max_output_tokens,
                ),
            )
            finish_reason = response.candidates[0].finish_reason
            if finish_reason == types.FinishReason.MAX_TOKENS:
                raise ValueError(
                    f"Gemini response truncated at max_output_tokens={max_output_tokens} "
                    "before the JSON completed — raise max_output_tokens and retry."
                )
            return TypeAdapter(response_schema).validate_json(response.text)
        except APIError as exc:
            if exc.code in _NON_RETRYABLE_HTTP_CODES:
                logger.error("Gemini call failed with a non-retryable error", exc_info=True)
                raise
            last_error = exc
        except (ValidationError, ConnectionError) as exc:
            last_error = exc

        if attempt < _MAX_ATTEMPTS - 1:
            delay = _BACKOFF_SECONDS[attempt]
            logger.warning(
                "Gemini call failed (attempt %d/%d), retrying in %ds: %s",
                attempt + 1, _MAX_ATTEMPTS, delay, last_error,
            )
            await asyncio.sleep(delay)
        else:
            logger.error("Gemini call failed after %d attempts", _MAX_ATTEMPTS, exc_info=True)

    assert last_error is not None
    raise last_error
