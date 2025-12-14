from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from typing import Dict, Any

from ..db import models
from ..core.logging import logger
from ..services.whatsapp import whatsapp_service
from .menu import MenuFlow
from .validation import is_menu_option, is_reserved, is_yes, is_no


class VolunteerFlow:
    def __init__(self, db: Session):
        self.db = db
        self.menu_flow = MenuFlow(db)

    def handle_food_type(self, phone: str, message: str) -> str:
        """Reuse state for volunteer region."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Informe o bairro/região onde pode atuar (ex: Rocinha, Centro)."
            )
            logger.info(f"[volunteer] STATE=VOLUNTEER_FOOD_TYPE INPUT='{cleaned}' ACCEPTED=False")
            return "VOLUNTEER_FOOD_TYPE"

        self._update_temp_data(phone, {"region": cleaned})
        logger.info(f"[volunteer] STATE=VOLUNTEER_FOOD_TYPE INPUT='{cleaned}' ACCEPTED=True")

        whatsapp_service.send_message(
            phone,
            "🕐 Qual a sua disponibilidade de horário? (ex: 18h-22h, fins de semana)"
        )
        return "VOLUNTEER_QTY"

    def handle_quantity(self, phone: str, message: str) -> str:
        """Reuse state for availability."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Informe sua disponibilidade (ex: 18h-22h, fins de semana)."
            )
            logger.info(f"[volunteer] STATE=VOLUNTEER_QTY INPUT='{cleaned}' ACCEPTED=False")
            return "VOLUNTEER_QTY"

        temp_data = self._get_temp_data(phone)
        temp_data["availability"] = cleaned
        self._update_temp_data(phone, temp_data)
        logger.info(f"[volunteer] STATE=VOLUNTEER_QTY INPUT='{cleaned}' ACCEPTED=True")

        whatsapp_service.send_message(
            phone,
            "🚗 Você tem transporte para ajudar nas entregas? Responda SIM ou NÃO."
        )
        return "VOLUNTEER_EXPIRES"

    def handle_expires_at(self, phone: str, message: str) -> str:
        """Reuse state for has transport (yes/no)."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip().lower()
        temp_data = self._get_temp_data(phone)

        if is_yes(cleaned):
            temp_data["has_transport"] = True
            accepted = True
        elif is_no(cleaned):
            temp_data["has_transport"] = False
            accepted = True
        else:
            accepted = False

        logger.info(f"[volunteer] STATE=VOLUNTEER_EXPIRES INPUT='{cleaned}' ACCEPTED={accepted}")

        if not accepted:
            whatsapp_service.send_message(
                phone,
                "Responda SIM ou NÃO para sabermos se você tem transporte."
            )
            return "VOLUNTEER_EXPIRES"

        self._update_temp_data(phone, temp_data)

        # Ask for location
        whatsapp_service.send_message(
            phone,
            "📍 Qual o ponto de referência principal? (ex: Praça da Sé, Centro)."
        )
        return "VOLUNTEER_LOCATION"

    def handle_location(self, phone: str, message: str) -> str:
        """Handle reference location and proceed to confirm."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Informe um ponto de referência (ex: Praça da Sé, Centro)."
            )
            logger.info(f"[volunteer] STATE=VOLUNTEER_LOCATION INPUT='{cleaned}' ACCEPTED=False")
            return "VOLUNTEER_LOCATION"

        temp_data = self._get_temp_data(phone)
        temp_data["location"] = cleaned
        self._update_temp_data(phone, temp_data)
        logger.info(f"[volunteer] STATE=VOLUNTEER_LOCATION INPUT='{cleaned}' ACCEPTED=True")

        summary = f"""
✅ CONFIRMAR CADASTRO DE VOLUNTÁRIO

🏙️ Região: {temp_data.get('region','')}
🕐 Disponibilidade: {temp_data.get('availability','')}
🚗 Transporte: {"Sim" if temp_data.get('has_transport') else "Não"}
📍 Referência: {temp_data.get('location','')}

Responda SIM para confirmar ou CANCELAR para encerrar."""

        whatsapp_service.send_message(phone, summary)
        return "VOLUNTEER_CONFIRM"

    def handle_confirm(self, phone: str, message: str) -> str:
        """Handle volunteer distribution confirmation."""
        message_lower = message.lower().strip()

        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        if is_yes(message_lower):
            temp_data = self._get_temp_data(phone)

            # Persiste em registro simples (demo)
            from ..services import volunteer_registry
            volunteer_registry.add_volunteer(
                {
                    "phone": phone,
                    "region": temp_data.get("region", ""),
                    "availability": temp_data.get("availability", ""),
                    "has_transport": temp_data.get("has_transport", False),
                    "location": temp_data.get("location", ""),
                }
            )

            self._update_user_role(phone, models.UserRole.VOLUNTEER)

            success_msg = f"""✅ Voluntário cadastrado!

🏙️ Região: {temp_data.get('region','')}
🕐 Disponibilidade: {temp_data.get('availability','')}
🚗 Transporte: {"Sim" if temp_data.get('has_transport') else "Não"}
📍 Referência: {temp_data.get('location','')}

Quando houver match na sua região, você será acionado.
Digite MENU para voltar."""

            whatsapp_service.send_message(phone, success_msg)

            self.menu_flow._update_state(phone, "VOLUNTEER_COMPLETED", None)
            logger.info(f"[volunteer] completed_flow=VOL phone={phone}")
            return "VOLUNTEER_COMPLETED"

        else:
            whatsapp_service.send_message(
                phone,
                "Não entendi. Responda SIM para confirmar ou CANCELAR para encerrar."
            )
            return "VOLUNTEER_CONFIRM"

    def _parse_expires_at(self, expires_text: str) -> datetime:
        """Parse expiration time from text (simple implementation)."""
        try:
            expires_lower = expires_text.lower()

            # Try to extract hour
            import re
            hour_match = re.search(r'(\d{1,2})[:\.]?(\d{2})?\s*h', expires_lower)
            if hour_match:
                hour = int(hour_match.group(1))
                minute = int(hour_match.group(2)) if hour_match.group(2) else 0

                # Assume today, adjust if past
                now = datetime.utcnow()
                expires = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                if expires <= now:
                    expires = expires + timedelta(days=1)

                return expires

            # Handle relative times
            if "hora" in expires_lower or "h" in expires_lower:
                hours_match = re.search(r'(\d+)\s*(?:hora|h)', expires_lower)
                if hours_match:
                    hours = int(hours_match.group(1))
                    return datetime.utcnow() + timedelta(hours=hours)

            # Default: 2 hours from now
            return datetime.utcnow() + timedelta(hours=2)

        except Exception as e:
            logger.warning(f"Could not parse expires_at '{expires_text}': {e}")
            return datetime.utcnow() + timedelta(hours=2)

    def _is_cancel_command(self, message: str) -> bool:
        """Check if message is a cancel command."""
        message_lower = message.lower().strip()
        return message_lower in ["cancelar", "c", "cancel", "❌"]

    def _cancel_flow(self, phone: str) -> str:
        """Cancel current flow and return to menu."""
        self._clear_temp_data(phone)
        whatsapp_service.send_message(phone, "❌ Distribuição cancelada.")
        self.menu_flow.show_menu(phone)
        return "MENU"

    def _get_temp_data(self, phone: str) -> Dict[str, Any]:
        """Get temporary conversation data."""
        state = self.menu_flow.get_current_state(phone)
        return state.temp_json if state else {}

    def _update_temp_data(self, phone: str, data: Dict[str, Any]) -> None:
        """Update temporary conversation data."""
        state = self.menu_flow.get_current_state(phone)
        if state:
            state.temp_json = data
            self.db.commit()

    def _clear_temp_data(self, phone: str) -> None:
        """Clear temporary conversation data."""
        self.menu_flow._clear_temp_data(phone)

    def _update_user_role(self, phone: str, role: str) -> None:
        """Update or create user with role."""
        user = self.db.query(models.User).filter(models.User.phone == phone).first()
        if user:
            user.role = role
        else:
            user = models.User(phone=phone, role=role)
            self.db.add(user)
        self.db.commit()


