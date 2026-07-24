from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from helpers.config import get_settings

settings = get_settings()

# async engine — uses asyncpg driver to talk to PostgreSQL without blocking
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# session factory — produces one AsyncSession per request
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    """
    All ORM models inherit from this Base.
    SQLAlchemy and Alembic use it to discover all tables.
    """
    pass


async def get_db():
    """FastAPI dependency — one DB session per request, auto-closed after."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    """Creates all tables on startup. For dev use — Alembic handles production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
