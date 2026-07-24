from sqlalchemy import Column, String, Float, UUID, ForeignKey
from helpers.db import Base
import uuid

class QuestionLOLink(Base):
    __tablename__ = "question_lo_links"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # foreign keys — link this row to a question and a learning outcome
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    lo_id       = Column(UUID(as_uuid=True), ForeignKey("learning_outcomes.id"), nullable=False)

    # how confident is the linker that this question maps to this LO (0.0 – 1.0)
    confidence  = Column(Float, nullable=False)

    # explanation of why this question was linked to this LO
    reason      = Column(String, nullable=False)
