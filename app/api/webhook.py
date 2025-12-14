import asyncio
import logging
import os
from datetime import datetime
from hashlib import sha256
from typing import Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.logging import logger
from ..db import models
from ..db.session import get_db
from ..flows.donate import DonateFlow
from ..flows.menu import MenuFlow
from ..flows.org import OrgFlow
from ..flows.seeker import SeekerFlow
from ..flows.volunteer import VolunteerFlow
from ..flows.commands import handle_global_commands, handle_menu_number_outside_menu
from ..services.matching import MatchingService
from ..services.whatsapp import whatsapp_service


router = APIRouter()
route_logger = logging.getLogger("uvicorn.error")


@router.post("")
async def bridge_webhook(payload: Dict, db: Session = Depends(get_db)) -> Response:
    """Entrada padrão para o Node (WPPConnect) repassar mensagens."""
    numero = (payload or {}).get("numero")
    mensagem = (payload or {}).get("mensagem")

    if not numero or not isinstance(numero, str) or not mensagem or not isinstance(mensagem, str):
        logger.warning("Payload inválido em /webhook", extra={"payload": payload})
        return JSONResponse(
            {"status": "erro", "detail": "numero e mensagem são obrigatórios"},
            status_code=400,
        )

    logger.info(f"📩 PROCESSANDO: {mensagem} (De: {numero})")

    try:
        result = await process_inbound_message(numero, mensagem, db)
    except Exception as exc:
        logger.exception(f"Erro ao processar mensagem inbound: {exc}")
        # fallback seguro: mostra menu e não retorna 500
        menu_fallback = "⚠️ Algo deu errado. Digite MENU para recomeçar."
        whatsapp_service.send_message(numero, menu_fallback)
        return JSONResponse({"status": "recebido", "debug": {"error": str(exc)}}, status_code=200)

    await _dispatch_messages_to_node(numero, result.get("reply"), result.get("outbox", []))

    return JSONResponse({"status": "recebido", "debug": result.get("debug")})


@router.api_route("/whatsapp", methods=["GET", "POST"], response_model=None)
async def whatsapp_webhook(
    request: Request,
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_mode_legacy: Optional[str] = Query(None, alias="hub_mode"),
    hub_verify_token_legacy: Optional[str] = Query(None, alias="hub_verify_token"),
    hub_challenge_legacy: Optional[str] = Query(None, alias="hub_challenge"),
    mode_plain: Optional[str] = Query(None, alias="mode"),
    verify_token_plain: Optional[str] = Query(None, alias="verify_token"),
    challenge_plain: Optional[str] = Query(None, alias="challenge"),
    db: Session = Depends(get_db)
) -> Response:
    """Handle WhatsApp webhook verification (GET) and messages (POST)."""
    if request.method == "GET":
        mode = hub_mode or hub_mode_legacy or mode_plain
        challenge = hub_challenge or hub_challenge_legacy or challenge_plain
        token = hub_verify_token or hub_verify_token_legacy or verify_token_plain

        logger.info(
            "Received WhatsApp webhook verification attempt",
            extra={"mode": mode, "has_challenge": challenge is not None},
        )

        env_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
        settings_token = settings.whatsapp_verify_token
        legacy_token = settings.verify_token

        if not env_token:
            logger.warning("WHATSAPP_VERIFY_TOKEN not set; using configured fallback token")

        expected_token = env_token or settings_token or legacy_token

        if mode is None and token is None and challenge is None:
            return PlainTextResponse(content="ok", status_code=200)

        if mode == "subscribe" and token and token == expected_token and challenge is not None:
            logger.info("WhatsApp webhook verification succeeded")
            return PlainTextResponse(content=str(challenge), status_code=200)

        logger.info("WhatsApp webhook verification failed", extra={"mode": mode})
        return PlainTextResponse(content="Forbidden", status_code=403)

    # POST branch
    try:
        payload = await request.json()
        logger.info(f"Received WhatsApp payload: {payload}")

        # Extract message data
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    await process_message(message, db)

        return JSONResponse({"status": "ok"})

    except Exception as e:
        logger.exception(f"Error processing WhatsApp webhook: {e}")
        return JSONResponse({"status": "ok"})


async def process_message(message: dict, db: Session) -> None:
    """Process a single WhatsApp message."""
    try:
        message_id = message.get("id")
        phone = message.get("from", "")
        text_body = (message.get("text", {}) or {}).get("body", "")
        message_type = message.get("type", "")

        if message_type != "text":
            _store_processed_message(db, message_id, phone)
            return

        text_body = (text_body or "").strip()
        if not phone or not text_body:
            _store_processed_message(db, message_id, phone)
            return

        await _handle_text_message(
            phone,
            text_body,
            db,
            dedupe_id=message_id,
            capture=False,
        )

    except Exception as e:
        logger.error(f"Error processing message from {message.get('from', '')}: {e}")


async def process_inbound_message(numero: str, mensagem: str, db: Session) -> Dict[str, object]:
    """Processa mensagens vindas do Node, retornando reply/outbox/debug."""
    result = await _handle_text_message(numero, mensagem, db, dedupe_id=None, capture=True)
    captured = result.get("captured", [])
    reply, outbox = _split_captured(numero, captured)

    debug = result.get("debug", {})
    debug.update({"captured_count": len(captured)})

    return {"reply": reply, "outbox": outbox, "debug": debug}


async def _handle_text_message(
    phone: str,
    text_body: str,
    db: Session,
    *,
    dedupe_id: Optional[str],
    capture: bool,
) -> Dict[str, object]:
    dedupe_id = dedupe_id or _build_fallback_message_id(phone, text_body)

    captured: List[Dict[str, str]] = []
    previous_sender = None

    if capture:
        def _capture(to: str, text: str) -> bool:
            captured.append({"to": to, "text": text})
            return True

        previous_sender = whatsapp_service.set_sender_override(_capture)

    try:
        if dedupe_id:
            existing = db.query(models.ProcessedMessage).filter(
                models.ProcessedMessage.message_id == dedupe_id
            ).first()
            if existing:
                logger.info(f"dedupe_hit: message_id={dedupe_id}")
                return {
                    "captured": captured,
                    "debug": {"dedupe_hit": True, "dedupe_id": dedupe_id},
                }

        logger.info(f"Processing message from {phone}: {text_body}")

        menu_flow = MenuFlow(db)
        donate_flow = DonateFlow(db)
        org_flow = OrgFlow(db)
        seeker_flow = SeekerFlow(db)
        volunteer_flow = VolunteerFlow(db)
        matching_service = MatchingService(db)

        current_state = menu_flow.get_current_state(phone)
        state = current_state.state if current_state else "MENU"
        logger.info(
            f"[inbound] phone={phone} text='{text_body}' state={state} dedupe_id={dedupe_id} capture={capture}"
        )
        route_logger.info(
            f"[route] phone={phone} incoming='{text_body}' prev_state={state} "
            f"temp={menu_flow._get_temp_data(phone) if hasattr(menu_flow,'_get_temp_data') else {}}"
        )

        text_lower = text_body.lower().strip()

        fastlane_cmds = {"oi", "olá", "ola", "menu", "reiniciar", "m"}
        if text_lower == "menu":
            menu_flow._clear_temp_data(phone)
            menu_flow.show_menu(phone, reason="fastlane:menu")
            _store_processed_message(db, dedupe_id, phone)
            return {
                "captured": captured,
                "debug": {"state": state, "next_state": "MENU", "fastlane": text_lower},
            }

        blocked_fastlane_prefixes = ("ORG_", "SEEK_", "VOLUNTEER_")
        if not state.startswith(blocked_fastlane_prefixes):
            if text_lower in fastlane_cmds:
                menu_flow._clear_temp_data(phone)
                menu_flow.show_menu(phone, reason=f"fastlane:{text_lower}")
                _store_processed_message(db, dedupe_id, phone)
                return {
                    "captured": captured,
                    "debug": {"state": state, "next_state": "MENU", "fastlane": text_lower},
                }

        if text_lower in ["cancelar", "c", "cancel"]:
            menu_flow._clear_temp_data(phone)
            menu_flow.show_menu(phone, reason="cancel")
            _store_processed_message(db, dedupe_id, phone)
            return {
                "captured": captured,
                "debug": {"state": state, "next_state": "MENU", "fastlane": text_lower},
            }

        # Global command: reiniciar
        next_state_global = handle_global_commands(phone, text_lower, state)
        if next_state_global:
            menu_flow._clear_temp_data(phone)
            menu_flow.show_menu(phone, reason=f"global:{text_lower}")
            _store_processed_message(db, dedupe_id, phone)
            return {
                "captured": captured,
                "debug": {"state": state, "next_state": "MENU", "fastlane": text_lower},
            }

        # Bloqueio de números do menu fora do MENU para UX melhor
        if state != "MENU":
            if handle_menu_number_outside_menu(phone, text_body, state):
                _store_processed_message(db, dedupe_id, phone)
                return {
                    "captured": captured,
                    "debug": {"state": state, "blocked_menu_number": True},
                }

        if matching_service.process_org_response(phone, text_body):
            _store_processed_message(db, dedupe_id, phone)
            return {"captured": captured, "debug": {"state": state, "org_response": True}}

        next_state = await route_by_state(
            state, phone, text_body, db,
            menu_flow, donate_flow, org_flow, seeker_flow, volunteer_flow
        )

        temp_data = menu_flow._get_temp_data(phone) if hasattr(menu_flow, "_get_temp_data") else {}
        is_prev_donate = state.startswith("DONATE_")
        is_next_donate = next_state.startswith("DONATE_")

        if is_prev_donate:
            route_logger.warning(
                f"[route][tripwire] prev_state is DONATE_*; skipping _update_state to avoid overwrite "
                f"phone={phone} incoming='{text_body}' prev_state={state} next_state={next_state} temp={temp_data}"
            )
        elif is_next_donate:
            route_logger.info(
                f"[route] phone={phone} incoming='{text_body}' prev_state={state} "
                f"next_state={next_state} temp_preserved=True temp={temp_data}"
            )
        else:
            menu_flow._update_state(phone, next_state, None)
            route_logger.info(
                f"[route] phone={phone} incoming='{text_body}' prev_state={state} "
                f"next_state={next_state} temp_preserved=True temp={temp_data}"
            )

        if not captured:
            fallback = "⚠️ Não entendi sua resposta.\nPor favor, responda conforme solicitado ou digite MENU para voltar."
            whatsapp_service.send_message(phone, fallback)
            captured.append({"to": phone, "text": fallback})

        _store_processed_message(db, dedupe_id, phone)
        logger.info(
            f"[state] phone={phone} prev_state={state} next_state={next_state} "
            f"dedupe_id={dedupe_id} reply_empty={len(captured)==0}"
        )
        return {
            "captured": captured,
            "debug": {
                "state": state,
                "next_state": next_state,
                "dedupe_id": dedupe_id,
            },
        }
    finally:
        if capture:
            whatsapp_service.set_sender_override(previous_sender)


def _build_fallback_message_id(phone: str, text_body: str) -> str:
    """Generate deterministic fallback message id when provider id is absent."""
    current_minute = datetime.utcnow().replace(second=0, microsecond=0).isoformat()
    seed = f"{phone}|{text_body}|{current_minute}"
    return sha256(seed.encode("utf-8")).hexdigest()


def _store_processed_message(db: Session, message_id: str, phone: str) -> None:
    """Persist processed message to avoid reprocessing."""
    if not message_id:
        return

    record = models.ProcessedMessage(
        message_id=message_id,
        phone=phone
    )
    db.add(record)
    try:
        db.commit()
        logger.info(f"dedupe_store: message_id={message_id}")
    except Exception as e:
        db.rollback()
        logger.warning(f"Could not store processed message {message_id}: {e}")


def _split_captured(numero: str, captured: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
    reply: Optional[str] = None
    outbox: List[Dict[str, str]] = []

    for msg in captured:
        target = msg.get("to")
        text = msg.get("text")
        if not target or not text:
            continue

        if target == numero and reply is None:
            reply = text
        else:
            outbox.append({"to": target, "text": text})

    return reply, outbox


async def _dispatch_messages_to_node(numero: str, reply: Optional[str], outbox: List[Dict[str, str]]) -> None:
    payloads: List[Dict[str, str]] = []

    if reply:
        payloads.append({"numero": numero, "mensagem": reply})

    for item in outbox:
        if item.get("to") and item.get("text"):
            payloads.append({"numero": item["to"], "mensagem": item["text"]})

    if not payloads:
        return

    async def _send(payload: Dict[str, str]) -> None:
        try:
            await asyncio.to_thread(
                requests.post,
                settings.node_send_url,
                json=payload,
                timeout=5,
            )
        except Exception as exc:
            logger.warning(f"Falha ao enviar para Node /send: {exc}", extra={"payload": payload})

    for payload in payloads:
        await _send(payload)

async def route_by_state(
    state: str, phone: str, message: str, db: Session,
    menu_flow: MenuFlow, donate_flow: DonateFlow, org_flow: OrgFlow,
    seeker_flow: SeekerFlow, volunteer_flow: VolunteerFlow
) -> str:
    """Route message to appropriate flow handler based on state."""

    # Menu state
    if state == "MENU":
        return menu_flow.handle_menu_choice(phone, message)

    # Donation flow
    elif state == "DONATE_FOOD_TYPE":
        return donate_flow.handle_food_type(phone, message)
    elif state == "DONATE_QTY":
        return donate_flow.handle_quantity(phone, message)
    elif state == "DONATE_EXPIRES":
        return donate_flow.handle_expires_at(phone, message)
    elif state == "DONATE_LOCATION":
        return donate_flow.handle_location(phone, message)
    elif state == "DONATE_CONFIRM":
        return donate_flow.handle_confirm(phone, message)
    elif state == "DONATE_POST_MATCH":
        msg_lower = (message or "").lower().strip()
        if msg_lower in ["menu", "m", "reiniciar"]:
            menu_flow.show_menu(phone, reason="post_match_menu")
            return "MENU"
        # Mantém o usuário no pós-doação até comando explícito
        return "DONATE_POST_MATCH"
    elif state.startswith("DONATE_"):
        # Fallback: ensure donation states stay within donation flow
        return donate_flow.handle_food_type(phone, message)

    # Organization flow
    elif state == "ORG_NAME":
        return org_flow.handle_name(phone, message)
    elif state == "ORG_COVERAGE":
        return org_flow.handle_coverage(phone, message)
    elif state == "ORG_PICKUP":
        return org_flow.handle_pickup(phone, message)
    elif state == "ORG_HOURS":
        return org_flow.handle_hours(phone, message)
    elif state == "ORG_CONFIRM":
        return org_flow.handle_confirm(phone, message)
    elif state == "ORG_COMPLETED":
        msg_lower = (message or "").lower().strip()
        if msg_lower in ["menu", "m", "reiniciar"]:
            menu_flow.show_menu(phone, reason="org_completed_menu")
            return "MENU"
        return "ORG_COMPLETED"

    # Seeker flow
    elif state == "SEEK_ITEM":
        return seeker_flow.handle_item(phone, message)
    elif state == "SEEK_LOCATION":
        return seeker_flow.handle_location(phone, message)
    elif state == "SEEK_COMPLETED":
        msg_lower = (message or "").lower().strip()
        if msg_lower in ["menu", "m", "reiniciar"]:
            menu_flow.show_menu(phone, reason="seek_completed_menu")
            return "MENU"
        return "SEEK_COMPLETED"

    # Volunteer flow
    elif state == "VOLUNTEER_FOOD_TYPE":
        return volunteer_flow.handle_food_type(phone, message)
    elif state == "VOLUNTEER_QTY":
        return volunteer_flow.handle_quantity(phone, message)
    elif state == "VOLUNTEER_EXPIRES":
        return volunteer_flow.handle_expires_at(phone, message)
    elif state == "VOLUNTEER_LOCATION":
        return volunteer_flow.handle_location(phone, message)
    elif state == "VOLUNTEER_CONFIRM":
        return volunteer_flow.handle_confirm(phone, message)
    elif state == "VOLUNTEER_COMPLETED":
        msg_lower = (message or "").lower().strip()
        if msg_lower in ["menu", "m", "reiniciar"]:
            menu_flow.show_menu(phone, reason="vol_completed_menu")
            return "MENU"
        return "VOLUNTEER_COMPLETED"

    # Unknown state - go back to menu
    else:
        menu_flow.show_menu(phone)
        return "MENU"
