from pydantic import BaseModel

class   LearningOutcome(BaseModel):
    source_evidence:str
    concept: str
    text:str
    id:str