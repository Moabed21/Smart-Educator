from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from helpers.config import get_settings

settings = get_settings()

# Async PostgreSQL engine with production connection pooling & pre-ping health verification
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
)

# Session factory producing isolated AsyncSessions per request
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative Base class for all SQLAlchemy ORM models."""
    pass


async def get_db():
    """FastAPI Dependency providing an async session per request with automatic cleanup."""
    async with AsyncSessionLocal() as session:
        yield session
