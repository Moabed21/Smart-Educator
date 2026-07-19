from pydantic import BaseModel

class QuestionConfig(BaseModel):
    mcq_count: int
    true_false_count: int
    short_answer_count: int
class DifficultyDistribution(BaseModel):
    easy: float      # e.g. 0.3
    medium: float    # e.g. 0.5
    hard: float      # e.g. 0.2
class EducationalContext(BaseModel):
    subject: str
    grade_level: str
    passage: str                             # the actual text content
    question_config: QuestionConfig
    difficulty_distribution: DifficultyDistribution 