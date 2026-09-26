"""Pydantic models for Educational Context, Question Configurations, and Difficulty.

Serves as the primary input contract for the LangGraph AI generation pipeline
(POST /api/v1/dataset/generate).
"""
from pydantic import BaseModel, Field, model_validator


class QuestionConfig(BaseModel):
    """
    Specifies how many questions of each supported format should be generated.
    
    EXPLANATION:
    - Field(ge=0): Validates that counts cannot be negative (ge = greater than or equal to).
    - @model_validator(mode="after"): Pydantic V2 cross-field validator. Runs after individual
      fields are type-checked. Ensures that the user requested at least 1 total question,
      preventing meaningless pipeline executions with 0 total questions requested.
    """
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
    """
    Defines the proportional breakdown of question difficulty (Bloom's Taxonomy).
    
    EXPLANATION:
    - Field(ge=0.0, le=1.0): Constrains each proportion between 0% and 100%.
    - @model_validator(mode="after"): Validates that the sum of proportions equals 1.0 (100%).
      Uses round(..., 2) to prevent floating-point rounding quirks (e.g. 0.3 + 0.3 + 0.4 = 1.0).
    """
    easy: float = Field(ge=0.0, le=1.0, description="Proportion of easy questions (e.g. 0.3)")
    medium: float = Field(ge=0.0, le=1.0, description="Proportion of medium questions (e.g. 0.5)")
    hard: float = Field(ge=0.0, le=1.0, description="Proportion of hard questions (e.g. 0.2)")

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> "DifficultyDistribution":
        total = round(self.easy + self.medium + self.hard, 2)
        if total != 1.0:
            raise ValueError(f"Difficulty percentages must sum to 1.0 (currently sum to {total}).")
        return self


class EducationalContext(BaseModel):
    """
    The core input payload required to initiate the AI assessment pipeline.
    
    EXPLANATION:
    - subject: Name of curriculum subject (e.g. "Biology", "Physics").
    - grade_level: Academic level (e.g. "Grade 10", "Undergraduate").
    - passage: The educational text/lesson source from which LOs and questions are grounded.
      Enforces min_length=50 to prevent hallucinations on trivial or empty inputs.
    - question_config: Nested QuestionConfig model specifying question counts.
    - difficulty_distribution: Nested DifficultyDistribution model defining target difficulties.
    """
    subject: str = Field(min_length=2, max_length=100, description="Curriculum subject")
    grade_level: str = Field(min_length=1, max_length=50, description="Target educational level")
    passage: str = Field(min_length=50, description="Educational passage text (at least 50 characters)")
    question_config: QuestionConfig
    difficulty_distribution: DifficultyDistribution