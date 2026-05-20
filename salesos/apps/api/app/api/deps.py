from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session


async def db_session() -> AsyncSession:
    async for session in get_db_session():
        return session
    raise RuntimeError("Database session could not be created")
