from sqlalchemy import Column, String, Float, UUID, ForeignKey
from helpers.db import Base
import uuid

class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # which question this evaluation belongs to
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)

    # the 8 PRD §8.5 criteria scores (0.0 – 1.0 each)
    context_grounding_score          = Column(Float, nullable=False)
    clarity_score                    = Column(Float, nullable=False)
    answer_correctness_score         = Column(Float, nullable=False)
    explanation_correctness_score    = Column(Float, nullable=False)
    learning_outcome_alignment_score = Column(Float, nullable=False)
    difficulty_score                 = Column(Float, nullable=False)
    question_type_validity_score     = Column(Float, nullable=False)
    choices_validity_score           = Column(Float, nullable=True)  # MCQ only — can be NULL

    # weighted average of all scores above
    overall_score = Column(Float, nullable=False)

    # accepted | rejected | needs_review
    status        = Column(String, nullable=False)