import pytest
import os
from services.file_service import chunk_text
from routes.schemes.educationalContext import EducationalContext, QuestionConfig, DifficultyDistribution


def test_multi_lesson_chunking():
    """
    Verifies that a multi-lesson document is cleanly chunked without loss of context,
    and each chunk preserves its core scientific concepts.
    """
    sample_file_path = os.path.join(os.path.dirname(__file__), "..", "assets", "multi_lesson_sample.txt")
    assert os.path.exists(sample_file_path), "Sample file must exist"

    with open(sample_file_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Split using the streamlined file_service chunker
    chunks = chunk_text(full_text, chunk_size=400, overlap_size=50)
    assert len(chunks) >= 3, "Should produce at least 3 distinct chunks for the 3 lessons"

    chunk_texts = [c["page_content"] for c in chunks]

    # Check that individual chunks isolate the distinct subjects
    has_physics = any("نيوتن" in c or "القصور الذاتي" in c for c in chunk_texts)
    has_chemistry = any("الروابط الأيونية" in c or "نموذج بور" in c for c in chunk_texts)
    has_biology = any("البناء الضوئي" in c or "الكلوروفيل" in c for c in chunk_texts)

    assert has_physics, "Physics chunk preserved"
    assert has_chemistry, "Chemistry chunk preserved"
    assert has_biology, "Biology chunk preserved"


def test_distinct_educational_contexts():
    """
    Verifies that chunks from different lessons create distinct EducationalContext
    objects with unique hash fingerprints.
    """
    from helpers.hashing import compute_context_hash

    physics_ctx = EducationalContext(
        subject="Physics",
        grade_level="Grade 10",
        passage="ينص قانون نيوتن الأول في الحركة على أن الجسم الساكن يبقى ساكناً.",
        question_config=QuestionConfig(mcq_count=2, true_false_count=1, short_answer_count=1),
        difficulty_distribution=DifficultyDistribution(easy=0.5, medium=0.3, hard=0.2)
    )

    biology_ctx = EducationalContext(
        subject="Biology",
        grade_level="Grade 10",
        passage="تقوم النباتات الخضراء بعملية البناء الضوئي داخل البلاستيدات الخضراء.",
        question_config=QuestionConfig(mcq_count=2, true_false_count=1, short_answer_count=1),
        difficulty_distribution=DifficultyDistribution(easy=0.5, medium=0.3, hard=0.2)
    )

    hash_physics = compute_context_hash(physics_ctx)
    hash_biology = compute_context_hash(biology_ctx)

    assert hash_physics != hash_biology, "Context hashes must be unique across lessons"
    assert len(hash_physics) == 64, "Context hash is SHA-256 (64 hex characters)"
