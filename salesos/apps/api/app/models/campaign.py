import uuid

from sqlalchemy import Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CampaignStatus
from salesos_shared.db import TimestampMixin, UUIDPrimaryKeyMixin


class Campaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status"),
        default=CampaignStatus.draft,
        nullable=False,
    )
    lead_query: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    message_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    leads: Mapped[list["Lead"]] = relationship(back_populates="campaign", lazy="selectin")
    outreach_logs: Mapped[list["OutreachLog"]] = relationship(back_populates="campaign", lazy="selectin")


Index("ix_campaigns_status", Campaign.status)
