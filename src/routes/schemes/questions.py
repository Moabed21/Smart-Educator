from pydantic import BaseModel
from typing import Optional
from enum import Enum

class QuestionType(str, Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"

class Question(BaseModel):
    question_text: str
    question_type: QuestionType
    choices: Optional[list[str]] = None      # only for MCQ
    correct_answer: str
    explanation: str
    difficulty: str                          # "easy" / "medium" / "hard"
    estimated_time_minutes: int
    related_LO_ids: list[str]
    source_evidence: str