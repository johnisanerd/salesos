from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, instance):
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def get_by_id(self, model, entity_id):
        result = await self.session.execute(select(model).where(model.id == entity_id))
        return result.scalar_one_or_none()
