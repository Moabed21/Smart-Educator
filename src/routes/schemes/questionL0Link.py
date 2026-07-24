from pydantic import BaseModel

class QuestionL0Link(BaseModel):
    confidence: float
    reason:str
