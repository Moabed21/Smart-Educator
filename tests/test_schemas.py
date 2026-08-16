import pytest
from pydantic import ValidationError

from routes.schemes.educationalContext import (
    DifficultyDistribution,
    EducationalContext,
    QuestionConfig,
)
from routes.schemes.learningOutcome import LearningOutcome
from routes.schemes.questions import Question, QuestionType


def test_question_config_valid():
    config = QuestionConfig(mcq_count=3, true_false_count=2, short_answer_count=1)
    assert config.mcq_count == 3
    assert config.true_false_count == 2
    assert config.short_answer_count == 1


def test_question_config_invalid_zero_total():
    with pytest.raises(ValidationError):
        QuestionConfig(mcq_count=0, true_false_count=0, short_answer_count=0)


def test_difficulty_distribution_valid():
    dist = DifficultyDistribution(easy=0.3, medium=0.5, hard=0.2)
    assert dist.easy == 0.3
    assert dist.medium == 0.5
    assert dist.hard == 0.2


def test_difficulty_distribution_invalid_sum():
    with pytest.raises(ValidationError):
        DifficultyDistribution(easy=0.5, medium=0.5, hard=0.5)


def test_educational_context_valid():
    ctx = EducationalContext(
        subject="Physics",
        grade_level="Grade 11",
        passage="This is a comprehensive passage describing the law of universal gravitation and mechanics." * 2,
        question_config=QuestionConfig(mcq_count=2, true_false_count=1, short_answer_count=0),
        difficulty_distribution=DifficultyDistribution(easy=0.4, medium=0.4, hard=0.2),
    )
    assert ctx.subject == "Physics"
    assert len(ctx.passage) >= 50


def test_educational_context_short_passage():
    with pytest.raises(ValidationError):
        EducationalContext(
            subject="Physics",
            grade_level="Grade 11",
            passage="Too short passage",
            question_config=QuestionConfig(mcq_count=1, true_false_count=0, short_answer_count=0),
            difficulty_distribution=DifficultyDistribution(easy=1.0, medium=0.0, hard=0.0),
        )


def test_learning_outcome_schema():
    lo = LearningOutcome(
        id="LO_001",
        text="أن يفسر الطالب ظاهرة الانكسار الضوئي",
        concept="انكسار الضوء",
        source_evidence="ينكسر الضوء عند انتقاله بين وسطين مختلفين في الكثافة الضوئية.",
    )
    assert lo.id == "LO_001"
    assert "انكسار" in lo.concept


def test_mcq_question_schema():
    q = Question(
        question_text="ما هي وحدة قياس القوة؟",
        question_type=QuestionType.MCQ,
        choices=["نيوتن", "جول", "واط", "باسكال"],
        correct_answer="نيوتن",
        explanation="وحدة قياس القوة في النظام الدولي هي النيوتن.",
        difficulty="easy",
        estimated_time_minutes=1,
        related_LO_ids=["LO_001"],
        source_evidence="تقاس القوة بوحدة النيوتن.",
    )
    assert q.question_type == QuestionType.MCQ
    assert len(q.choices) == 4
    assert q.correct_answer in q.choices
