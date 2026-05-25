from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class LeadState(str, enum.Enum):
    NEW = "NEW"
    OUTREACHED = "OUTREACHED"
    WARM = "WARM"
    PORTFOLIO_SENT = "PORTFOLIO_SENT"
    READY_FOR_CALL = "READY_FOR_CALL"
    CALL_SCHEDULED = "CALL_SCHEDULED"
    FOLLOW_UP_1 = "FOLLOW_UP_1"
    FOLLOW_UP_3 = "FOLLOW_UP_3"
    FOLLOW_UP_7 = "FOLLOW_UP_7"
    FOLLOW_UP_14 = "FOLLOW_UP_14"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"
    ARCHIVED = "ARCHIVED"
    INVALID = "INVALID"


class MessageDirection(str, enum.Enum):
    IN = "in"
    OUT = "out"


class OutreachStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wa_number: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(128))
    clinic_name: Mapped[str | None] = mapped_column(String(256))
    clinic_type: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[LeadState] = mapped_column(
        SAEnum(LeadState, name="lead_state"), default=LeadState.NEW, nullable=False, index=True
    )
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    meta_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="Conversation.created_at"
    )
    state_logs: Mapped[list[StateLog]] = relationship(
        back_populates="lead", cascade="all, delete-orphan", order_by="StateLog.created_at"
    )
    outreach_jobs: Mapped[list[OutreachQueue]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    direction: Mapped[MessageDirection] = mapped_column(
        SAEnum(MessageDirection, name="message_direction"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    llm_model: Mapped[str | None] = mapped_column(String(128))
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    wa_message_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="conversations")


class StateLog(Base):
    __tablename__ = "state_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    from_state: Mapped[LeadState | None] = mapped_column(SAEnum(LeadState, name="lead_state"))
    to_state: Mapped[LeadState] = mapped_column(SAEnum(LeadState, name="lead_state"), nullable=False)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="state_logs")


class OutreachQueue(Base):
    __tablename__ = "outreach_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[OutreachStatus] = mapped_column(
        SAEnum(OutreachStatus, name="outreach_status"),
        default=OutreachStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    lead: Mapped[Lead] = relationship(back_populates="outreach_jobs")
