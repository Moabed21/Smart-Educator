# EducationalContext is the API input payload — it is NOT stored as a DB table.
# The context hash is stored in learning_outcomes.context_hash for deduplication.
# The full context object lives in: src/routes/schemes/educationalContext.py (Pydantic schema)