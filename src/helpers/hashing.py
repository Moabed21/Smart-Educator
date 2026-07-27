import hashlib
from routes.schemes.educationalContext import EducationalContext


def compute_context_hash(context: EducationalContext) -> str:
    """
    sha256(passage + question_config) — the canonical cache/dedup key
    for one educational context + its generation settings.

    Shared between:
    - graph/graph.py's parse_node (LO dedup column on learning_outcomes)
    - P3's Redis caching layer (cache key for POST /dataset/generate)

    Must stay byte-for-byte identical in both places, or the same input
    will hash differently depending on which caller computed it.
    """
    payload = context.passage + context.question_config.model_dump_json()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()