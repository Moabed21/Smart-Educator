"""Pydantic schema for extracted Learning Outcomes (LOs).

Defines the structure returned by Google Gemini during Node 2 of the pipeline
(services/lo_extraction.py).
"""
from pydantic import BaseModel


class LearningOutcome(BaseModel):
    """
    An atomic educational learning outcome extracted from curriculum text.
    
    EXPLANATION OF FIELDS:
    - id: Stable unique identifier for the outcome within the context (e.g. "LO-1").
    - concept: High-level academic topic or core subject principle (e.g. "Photosynthesis Equations").
    - text: Pedagogical statement of what the student should know or be able to do.
    - source_evidence: A verbatim quote copied directly from the original passage.
      This acts as an audit trail proving the outcome is factually grounded without LLM fabrication.
    """
    id: str
    concept: str
    text: str
    source_evidence: str