from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import LeadState, MessageDirection, OutreachStatus


class WebhookMessageIn(BaseModel):
    wa_number: str
    body: str
    timestamp: int | None = None
    message_id: str | None = None
    reply_jid: str | None = None


class WebhookMessageOut(BaseModel):
    reply: str
    state: LeadState
    skipped: bool = False
    reason: str | None = None


class LeadOut(BaseModel):
    id: int
    wa_number: str
    name: str | None
    clinic_name: str | None
    clinic_type: str | None
    city: str | None
    state: LeadState
    last_inbound_at: datetime | None
    last_outbound_at: datetime | None
    next_followup_at: datetime | None
    note: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class LeadStateUpdate(BaseModel):
    state: LeadState
    note: str | None = None


class LeadNoteUpdate(BaseModel):
    note: str


class ConversationOut(BaseModel):
    id: int
    direction: MessageDirection
    body: str
    llm_model: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class LLMReply(BaseModel):
    reply: str
    detected_intent: str | None = None
    suggested_state: LeadState | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
