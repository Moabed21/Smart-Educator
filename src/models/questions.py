from sqlalchemy import  Column, Integer, String, JSON, UUID
from helpers.db import Base
import uuid

class Questions(Base):
    __tablename__ = "questions"

    id =           Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_text= Column(String, nullable=False)
    question_type= Column(String, nullable=False)
    choices=       Column(JSON,   nullable=True)   # None for True/False and Short Answer
    correct_answer=Column(String, nullable=False)
    explanation=   Column(String, nullable=False)
    difficulty=    Column(String, nullable=False)
    estimated_time_minutes= Column(Integer, nullable=False)
    related_LO_ids=Column(JSON, nullable=False)
    source_evidence=Column(String, nullable=False)
