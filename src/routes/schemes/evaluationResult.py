"""Pydantic schemas for Question Evaluation & LLM-as-Judge scoring.

Defines the structure for the 8-criteria evaluation matrix and status classification
performed during Node 5 of the LangGraph pipeline.
"""
from pydantic import BaseModel
from typing import Optional
from enum import Enum


class EvaluationStatus(str, Enum):
	"""
	Validation decision statuses for generated questions.
	
	EXPLANATION:
	- Inheriting from (str, Enum) enables automatic JSON serialization in FastAPI
	  and direct compatibility with PostgreSQL VARCHAR/Enum column types.
	- ACCEPTED: Question passed all 8 criteria with high fidelity.
	- NEEDS_REVIEW: Marginal score (e.g. minor wording ambiguity) but structurally sound.
	- REJECTED: Failed critical criteria (e.g. factual error, hallucination, or no evidence).
	"""
	ACCEPTED = "accepted"
	REJECTED = "rejected"
	NEEDS_REVIEW = "needs_review"


class EvaluationResult(BaseModel):
    """
    Detailed 8-criteria pedagogical evaluation breakdown for a question.
    
    CRITERIA EXPLANATION (Each score ranges from 0.0 to 1.0):
    1. context_grounding_score: Is the question strictly factual and grounded in the source passage?
    2. clarity_score: Is the phrasing clear, grammatically sound, and unambiguous?
    3. answer_correctness_score: Is the designated correct answer undeniably true?
    4. explanation_correctness_score: Does the explanation accurately justify why the answer is correct?
    5. learning_outcome_alignment_score: Does the question effectively measure the linked Learning Outcome?
    6. difficulty_score: Does the question match its declared difficulty level (easy/medium/hard)?
    7. question_type_validity_score: Does it adhere to the format rules of its type (e.g. T/F binary)?
    8. choices_validity_score: Are multiple-choice distractors plausible and distinct? (None for non-MCQs).
    """
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