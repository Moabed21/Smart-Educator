from pydantic import BaseModel
from typing import Optional

class RecommendationRequest(BaseModel):
    query: str
    top_k: int = 5
    difficulty: Optional[str] = None