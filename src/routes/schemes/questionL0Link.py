"""Pydantic schema for Question-to-LO semantic linkage.

Represents the alignment result between an assessment question and a target
learning outcome produced during Node 4 of the pipeline (services/lo_linker.py).
"""
from pydantic import BaseModel


class QuestionL0Link(BaseModel):
    """
    Semantic alignment metric linking a question to an educational outcome.
    
    EXPLANATION OF FIELDS:
    - confidence: Cosine similarity score (between 0.0 and 1.0) calculated from
      3072-dimensional Gemini embeddings of the question text and LO statement.
    - reason: Pedagogical rationale explaining how the question tests this specific outcome.
    """
    confidence: float
    reason: str

