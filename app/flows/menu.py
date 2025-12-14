import unicodedata
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional

from ..db import models
from ..core.logging import logger
from ..services.whatsapp import whatsapp_service
from .state_store import set_state_and_temp, ensure_state_row, get_temp, _infer_flow_from_state


def _strip_accents(s: str) -> str:
    if not s:
        return ""
    normalized = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def is_donate_intent(text: str) -> bool:
    if not text:
        return False
    cleaned = " ".join(text.lower().strip().split())
    cleaned = _strip_accents(cleaned)
    intents = {
        "doar",
        "doacao",
        "quero doar",
        "tenho doacao",
        "fazer doacao",
    }
    if cleaned in intents:
        return True
    return "doar" in cleaned or "doacao" in cleaned


class MenuFlow:
    def __init__(self, db: Session):
        self.db = db

    def show_menu(self, phone: str, *, reason: str = "manual") -> None:
        """Show the main menu to the user."""
        menu_message = """Olá! Como posso te ajudar hoje?

1️⃣ Quero doar comida
2️⃣ Sou ONG / projeto social
3️⃣ Preciso de comida
4️⃣ Sou voluntário (distribuição agora)

Digite o número da opção ou escreva sua dúvida."""

        whatsapp_service.send_message(phone, menu_message)

        # Update conversation state
        self._update_state(phone, "MENU", {})
        logger.info(f"[menu] emitido para phone={phone} reason={reason}")

    def handle_menu_choice(self, phone: str, message: str) -> Optional[str]:
        """Handle user's menu choice and return the next state."""
        message_lower = message.lower().strip()

        # Handle menu commands
        if message_lower in ["menu", "m"]:
            self.show_menu(phone)
            return "MENU"

        if message_lower in ["cancelar", "c", "cancel"]:
            self._clear_temp_data(phone)
            self.show_menu(phone)
            return "MENU"

        # Handle menu options
        if message in ["1", "1️⃣"] or is_donate_intent(message):
            # Reset temp data and prompt first question of donation flow
            set_state_and_temp(self.db, phone, state="DONATE_FOOD_TYPE", clear_temp=True)
            whatsapp_service.send_message(
                phone,
                "🍽️ O que você quer doar? (ex: marmitas, frutas, pães)"
            )
            return "DONATE_FOOD_TYPE"

        elif message in ["2", "2️⃣"] or any(word in message_lower for word in ["ong", "organização", "projeto"]):
            whatsapp_service.send_message(
                phone,
                "Digite o NOME do projeto/ONG (ex: Cozinha Solidária X, ONG Esperança)."
            )
            self._update_state(phone, "ORG_NAME")
            return "ORG_NAME"

        elif message in ["3", "3️⃣"] or any(word in message_lower for word in ["preciso", "comida", "fome"]):
            whatsapp_service.send_message(
                phone,
                "O que você precisa? (ex: marmita, cesta básica)."
            )
            self._update_state(phone, "SEEK_ITEM")
            return "SEEK_ITEM"

        elif message in ["4", "4️⃣"] or any(word in message_lower for word in ["voluntário", "distribuir", "entregar"]):
            whatsapp_service.send_message(
                phone,
                "Informe o bairro/região onde pode atuar (ex: Rocinha, Centro)."
            )
            self._update_state(phone, "VOL_REGION")
            return "VOL_REGION"

        # Unknown choice - show menu again
        self.show_menu(phone)
        return "MENU"

    def _update_state(self, phone: str, state: str, temp_json: Optional[Dict[str, Any]] = None) -> None:
        """Update conversation state for a phone number, preserving temp_json when not provided."""
        row = ensure_state_row(self.db, phone)
        if temp_json is not None:
            row.payload = temp_json
            row.temp_json = temp_json
        row.state = state
        row.current_step = state
        row.current_flow = _infer_flow_from_state(state)
        self.db.commit()

    def _clear_temp_data(self, phone: str) -> None:
        """Clear temporary conversation data."""
        row = ensure_state_row(self.db, phone)
        row.payload = {}
        row.temp_json = {}
        self.db.commit()

    def get_current_state(self, phone: str) -> Optional[models.ConversationState]:
        """Get current conversation state for a phone."""
        return self.db.query(models.ConversationState).filter(
            models.ConversationState.phone == phone
        ).first()

    def _get_temp_data(self, phone: str) -> Dict[str, Any]:
        """Return temp_json for current conversation (helper for state updates)."""
        return get_temp(self.db, phone)
