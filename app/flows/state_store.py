from __future__ import annotations

import json
from typing import Any, Dict, Optional, Union

from sqlalchemy.orm import Session
from app.db import models

DEFAULT_STATE = "MENU"
DEFAULT_FLOW = "MENU"


def ensure_state_row(db: Session, phone: str) -> models.ConversationState:
    row = db.query(models.ConversationState).filter(models.ConversationState.phone == phone).first()
    if not row:
        row = models.ConversationState(
            phone=phone,
            state=DEFAULT_STATE,
            current_flow=DEFAULT_FLOW,
            current_step=DEFAULT_STATE,
            temp_json={},
            payload={},
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _to_dict(v: Union[dict, str, None]) -> Dict[str, Any]:
    if v is None:
        return {}
    if isinstance(v, dict):
        return dict(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _dump_like(original: Union[dict, str, None], data: Dict[str, Any]) -> Union[dict, str]:
    if isinstance(original, dict):
        return data
    return json.dumps(data, ensure_ascii=False)


def load_state(db: Session, phone: str) -> models.ConversationState:
    return ensure_state_row(db, phone)


def get_temp(db: Session, phone: str) -> Dict[str, Any]:
    row = ensure_state_row(db, phone)
    # Prefer payload, fallback to temp_json
    payload = _to_dict(row.payload)
    if payload:
        return payload
    return _to_dict(row.temp_json)


def reset_state(db: Session, phone: str) -> models.ConversationState:
    row = ensure_state_row(db, phone)
    row.state = DEFAULT_STATE
    row.current_flow = DEFAULT_FLOW
    row.current_step = DEFAULT_STATE
    row.temp_json = {}
    row.payload = {}
    db.commit()
    db.refresh(row)
    return row


def set_state_and_temp(
    db: Session,
    phone: str,
    *,
    state: str,
    temp: Optional[Dict[str, Any]] = None,
    clear_temp: bool = False,
) -> models.ConversationState:
    row = ensure_state_row(db, phone)
    original = row.temp_json
    current = _to_dict(row.payload or row.temp_json)

    if clear_temp:
        current = {}
    if temp is not None:
        current = dict(temp)

    row.state = state
    row.current_step = state
    row.current_flow = _infer_flow_from_state(state)
    row.temp_json = _dump_like(original, current)
    row.payload = current
    db.commit()
    db.refresh(row)
    return row


def merge_temp_and_advance(
    db: Session,
    phone: str,
    *,
    patch: Dict[str, Any],
    next_state: str,
) -> models.ConversationState:
    row = ensure_state_row(db, phone)
    original = row.temp_json
    current = _to_dict(row.payload or row.temp_json)

    for k, v in patch.items():
        if v is not None:
            current[k] = v

    row.state = next_state
    row.current_step = next_state
    row.current_flow = _infer_flow_from_state(next_state)
    row.temp_json = _dump_like(original, current)
    row.payload = current
    db.commit()
    db.refresh(row)
    return row


def _infer_flow_from_state(state: str) -> str:
    if state.startswith("DONATE"):
        return "DONATE"
    if state.startswith("ORG"):
        return "ORG"
    if state.startswith("SEEK"):
        return "SEEK"
    if state.startswith("VOL"):
        return "VOL"
    return "MENU"

