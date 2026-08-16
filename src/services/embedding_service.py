import hashlib
import json
from google import genai
from helpers.config import get_settings
from helpers.redis_client import get_cached, set_cached

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Lazily create the genai.Client, configured with GEMINI_API_KEY, once per process."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().GEMINI_API_KEY)
    return _client

settings = get_settings()
_EMBEDDING_MODEL = "gemini-embedding-001"
_CACHE_TTL_SECONDS = settings.REDIS_TTL  # 24 hours


def _make_cache_key(text: str) -> str:
    """
    Build a cache key from the text + model version, so that if we
    switch embedding models later, old cached vectors won't be reused.
    """
    raw = f"{text}:{_EMBEDDING_MODEL}"
    return "embedding:" + hashlib.sha256(raw.encode()).hexdigest()


async def embed_text(text: str) -> list[float]:
    """
    Convert a single piece of text into an embedding vector.
    Checks Redis first; only calls Gemini on a cache miss.
    """
    cache_key = _make_cache_key(text)

    cached = await get_cached(cache_key)
    if cached is not None:
        return json.loads(cached)

    result = await _get_client().aio.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=text,
    )
    embedding = result.embeddings[0].values

    await set_cached(cache_key, json.dumps(embedding), ttl_seconds=_CACHE_TTL_SECONDS)
    return embedding


async def embed_batch(texts: list[str]) -> list[list[float]]:
    """
    Convert multiple texts into embeddings in one call (more efficient
    than calling embed_text() in a loop). Not cached — used for bulk
    operations where texts are usually new each time.
    """
    result = await _get_client().aio.models.embed_content(
        model=_EMBEDDING_MODEL,
        contents=texts,
    )
    return [item.values for item in result.embeddings]