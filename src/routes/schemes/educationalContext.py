from pydantic import BaseModel, Field, model_validator

class QuestionConfig(BaseModel):
    # these upgrades of input validation are for edgecases ex. mcq < 0
    mcq_count: int = Field(ge=0, description="Number of MCQs to generate (must be >= 0)")
    true_false_count: int = Field(ge=0, description="Number of True/False questions (must be >= 0)")
    short_answer_count: int = Field(ge=0, description="Number of Short Answer questions (must be >= 0)")

    @model_validator(mode="after")
    # this function is called under the hood on every request (no need to call it yourself).
    def validate_total_questions(self) -> "QuestionConfig":
        total = self.mcq_count + self.true_false_count + self.short_answer_count
        if total <= 0:
            raise ValueError("At least one question type must have a count greater than 0.")
        return self


class DifficultyDistribution(BaseModel):
    easy: float = Field(ge=0.0, le=1.0)     # e.g. 0.3
    medium: float = Field(ge=0.0, le=1.0)   # e.g. 0.5
    hard: float = Field(ge=0.0, le=1.0)     # e.g. 0.2

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> "DifficultyDistribution":
        total = round(self.easy + self.medium + self.hard, 2)
        if total != 1.0:
            raise ValueError(f"Difficulty percentages must sum to 1.0 (currently sum to {total}).")
        return self


class EducationalContext(BaseModel):
    subject: str = Field(min_length=2, max_length=100)
    grade_level: str = Field(min_length=1, max_length=50)
    passage: str = Field(min_length=50, description="Educational passage text (at least 50 characters)")
    question_config: QuestionConfig
    difficulty_distribution: DifficultyDistribution