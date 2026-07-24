from sqlalchemy import Column, String, UUID
from helpers.db import Base
import uuid

class LearningOutcome(Base):
    __tablename__ = "learning_outcomes"

    # primary key
    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # content fields — all required, come directly from Gemini LO extraction
    text           = Column(String, nullable=False)   # full LO statement
    concept        = Column(String, nullable=False)   # core concept being tested
    source_evidence = Column(String, nullable=False)  # passage excerpt that supports this LO

    # used by Redis + DB to detect if this context was already processed
    # which saves resources by preventing AI api request duplication
    context_hash   = Column(String, nullable=False, index=True)