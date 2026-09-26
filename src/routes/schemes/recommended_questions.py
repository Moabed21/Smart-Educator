"""Pydantic schema for Vector Recommendation Requests.

Defines the parameters for semantic search queries executed against the
ChromaDB vector database (POST /api/v1/recommendations/questions).
"""
from pydantic import BaseModel
from typing import Optional


class RecommendationRequest(BaseModel):
    """
    Search request payload for semantic question recommendation.
    
    EXPLANATION OF FIELDS:
    - query: User search query or student's diagnosed weak learning outcome topic.
      This query is converted into a 3072-dimensional Gemini vector embedding.
    - top_k: Maximum number of nearest-neighbor questions to return (default: 5).
    - difficulty: Optional filter to restrict returned questions to a specific difficulty level.
    """
    query: str
    top_k: int = 5
    difficulty: Optional[str] = None