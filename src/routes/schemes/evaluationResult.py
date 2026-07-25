from pydantic import BaseModel
from typing import Optional
from enum import Enum

class EvaluationStatus(str,Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

class EvaluationResult(BaseModel):
    context_grounding_score: float
    clarity_score: float
    answer_correctness_score: float
    explanation_correctness_score: float
    learning_outcome_alignment_score: float
    difficulty_score: float
    question_type_validity_score: float
    choices_validity_score: Optional[float] = None   # MCQ only
    overall_score: float
    status: EvaluationStatus