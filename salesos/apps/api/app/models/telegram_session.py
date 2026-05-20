from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class TelegramSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "telegram_sessions"

    chat_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


Index("ix_telegram_sessions_user_id", TelegramSession.user_id)
