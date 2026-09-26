"""CRUD operations for the Questions table.

Handles database persistence and retrieval for assessment questions generated
by the Gemini AI pipeline, utilizing SQLAlchemy 2.0 async syntax.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from models.questions import Questions


async def save_questions(db: AsyncSession, questions: list[Questions]) -> None:
    """
    Bulk insert questions after Gemini generates them.
    Each question should already have all fields populated by the AI pipeline.
    
    EXPLANATION:
    - db.add_all(questions): Stages all Question ORM instances in the session memory.
    - await db.flush(): Sends SQL INSERT commands to PostgreSQL within the open
      transaction. This assigns database-generated IDs/defaults without permanently
      ending the transaction. If an error occurs, the transaction can roll back cleanly.
    - await db.commit(): Permanently commits the transaction to the database disk.
    """
    if not questions:
        return
    db.add_all(questions)
    await db.flush()
    # flush prevents closing the transaction if any error occurs and make a rollback
    # commit closes the transaction permanently.
    await db.commit()


async def get_question_by_id(db: AsyncSession, question_id) -> Questions | None:
    """
    Fetch a single question by its UUID — used by evaluation and linking.
    
    EXPLANATION:
    - select(Questions).where(...): Standard SQLAlchemy 2.0 declarative query construction.
    - db.execute(...): Asynchronously executes the query over the asyncpg connection.
    - scalar_one_or_none(): Extracts the single ORM object from the result row.
      Returns None if no matching question is found, or raises an error if multiple match.
    """
    result = await db.execute(
        select(Questions).where(Questions.id == question_id)
    )
    # scalar_one_or_none means return single unique object, if not exists return none
    return result.scalar_one_or_none()


async def get_all_questions(db: AsyncSession) -> list[Questions]:
    """
    Fetch all questions — used by embedding pipeline and dataset export.
    
    EXPLANATION:
    - result.scalars().all(): Queries return rows of tuples by default.
      Calling .scalars() unwraps the first column of each row (the Questions instance),
      and .all() materializes the result into a clean Python list of Question objects.
    """
    result = await db.execute(select(Questions))
    # scalar.all means return list of python objects, used when querying multiple items
    # items like here
    return result.scalars().all()


async def get_accepted_questions(db: AsyncSession) -> list[Questions]:
    """
    Fetch only questions with accepted/needs_review evaluations.
    Used by:
    - GET /dataset/export (only clean data)
    - Embedding pipeline (only embed approved questions)

    Joins with evaluation_results to filter by status and ensures distinct questions.
    
    EXPLANATION:
    - .join(EvaluationResult, ...): Performs an INNER JOIN on question_id foreign key.
    - .where(EvaluationResult.status.in_(...)): Filters out discarded/rejected questions.
    - .group_by(Questions.id): Ensures questions are not duplicated if multiple
      evaluation rounds exist for the same question.
    """
    from models.evaluationResult import EvaluationResult

    result = await db.execute(
        select(Questions)
        .join(EvaluationResult, EvaluationResult.question_id == Questions.id)
        .where(EvaluationResult.status.in_(["accepted", "needs_review"]))
        .group_by(Questions.id)
    )
    return result.scalars().all()


async def get_questions_by_ids(db: AsyncSession, question_ids: list) -> list[Questions]:
    """
    Bulk fetch multiple questions by a list of UUIDs.
    
    EXPLANATION:
    - Solving the N+1 query latency problem: Instead of querying the database
      in a loop N times for N question IDs (N network roundtrips),
      we issue a single SQL `WHERE id IN (...)` query to fetch all questions in 1 roundtrip.
    """
    # Solving the N+1 query latency problem
    if not question_ids:
        return []
    result = await db.execute(
        select(Questions).where(Questions.id.in_(question_ids))
    )
    return result.scalars().all()


