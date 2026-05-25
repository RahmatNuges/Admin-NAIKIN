from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Lead, LeadState
from app.schemas import LeadNoteUpdate, LeadOut, LeadStateUpdate

router = APIRouter(prefix="/admin")


class LeadProfileUpdate(BaseModel):
    name: str | None = None
    clinic_name: str | None = None
    clinic_type: str | None = None
    city: str | None = None
    source: str | None = None


def _require_admin(x_admin_token: str | None) -> None:
    s = get_settings()
    if not s.backend_admin_token or s.backend_admin_token == "change-me":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BACKEND_ADMIN_TOKEN not configured",
        )
    if x_admin_token != s.backend_admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


@router.get("/leads", response_model=list[LeadOut])
def list_leads(
    state: LeadState | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    _require_admin(x_admin_token)
    q = db.query(Lead)
    if state:
        q = q.filter(Lead.state == state)
    return q.order_by(Lead.updated_at.desc()).limit(limit).all()


@router.get("/leads/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: int,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    _require_admin(x_admin_token)
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    return lead


@router.patch("/leads/{lead_id}/profile", response_model=LeadOut)
def update_profile(
    lead_id: int,
    payload: LeadProfileUpdate,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    _require_admin(x_admin_token)
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/leads/{lead_id}/state", response_model=LeadOut)
def override_state(
    lead_id: int,
    payload: LeadStateUpdate,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    _require_admin(x_admin_token)
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    from app.models import StateLog

    db.add(
        StateLog(
            lead_id=lead.id,
            from_state=lead.state,
            to_state=payload.state,
            trigger="manual",
            note=payload.note,
        )
    )
    lead.state = payload.state
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/leads/{lead_id}/note", response_model=LeadOut)
def set_note(
    lead_id: int,
    payload: LeadNoteUpdate,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
):
    _require_admin(x_admin_token)
    lead = db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    lead.note = payload.note
    db.commit()
    db.refresh(lead)
    return lead
