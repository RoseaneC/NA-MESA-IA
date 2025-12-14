from sqlalchemy.orm import Session
from typing import Dict, Any

from ..db import models
from ..core.logging import logger
from ..services.whatsapp import whatsapp_service
from ..services.normalization import normalize_phone
from .menu import MenuFlow
from .validation import (
    is_valid_name,
    is_menu_option,
    is_reserved,
    is_yes,
    is_no,
)


class OrgFlow:
    def __init__(self, db: Session):
        self.db = db
        self.menu_flow = MenuFlow(db)

    def handle_name(self, phone: str, message: str) -> str:
        """Handle organization name input."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        accepted = is_valid_name(cleaned)
        logger.info(f"[org] STATE=ORG_NAME INPUT='{cleaned}' ACCEPTED={accepted}")
        if not accepted:
            whatsapp_service.send_message(
                phone,
                "Preciso do NOME do projeto/ONG (ex: Cozinha Solidária X, ONG Esperança)."
            )
            return "ORG_NAME"

        # Store name in temp data
        self._update_temp_data(phone, {"name": cleaned})

        # Ask for coverage area
        whatsapp_service.send_message(
            phone,
            "🏙️ Quais bairros ou regiões vocês atendem?\n\nExemplo: Centro, Vila Mariana, Pinheiros"
        )
        return "ORG_COVERAGE"

    def handle_coverage(self, phone: str, message: str) -> str:
        """Handle coverage area input."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Descreva os bairros/regiões atendidos (ex: Centro, Vila Mariana)."
            )
            logger.info(f"[org] STATE=ORG_COVERAGE INPUT='{cleaned}' ACCEPTED=False")
            return "ORG_COVERAGE"

        # Store coverage area
        temp_data = self._get_temp_data(phone)
        temp_data["coverage_area"] = cleaned
        self._update_temp_data(phone, temp_data)
        logger.info(f"[org] STATE=ORG_COVERAGE INPUT='{cleaned}' ACCEPTED=True")

        # Ask if they can pickup
        whatsapp_service.send_message(
            phone,
            "🚗 Conseguem buscar doações?\n\nResponda SIM ou NÃO"
        )
        return "ORG_PICKUP"

    def handle_pickup(self, phone: str, message: str) -> str:
        """Handle pickup capability input."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        message_lower = (message or "").lower().strip()

        # Store pickup capability
        temp_data = self._get_temp_data(phone)
        if is_yes(message_lower):
            temp_data["can_pickup"] = True
            accepted = True
        elif is_no(message_lower):
            temp_data["can_pickup"] = False
            accepted = True
        else:
            accepted = False

        logger.info(f"[org] STATE=ORG_PICKUP INPUT='{message_lower}' ACCEPTED={accepted}")

        if not accepted:
            whatsapp_service.send_message(
                phone,
                "Responda SIM ou NÃO para sabermos se conseguem buscar doações."
            )
            return "ORG_PICKUP"

        self._update_temp_data(phone, temp_data)

        # Ask for operating hours
        whatsapp_service.send_message(
            phone,
            "🕐 Quais os horários de funcionamento?\n\nExemplo: Segunda a sexta, 8h às 18h"
        )
        return "ORG_HOURS"

    def handle_hours(self, phone: str, message: str) -> str:
        """Handle operating hours input and create organization."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        # Store hours and create organization
        temp_data = self._get_temp_data(phone)
        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Informe os horários de funcionamento (ex: Seg a Sex 8h-18h)."
            )
            logger.info(f"[org] STATE=ORG_HOURS INPUT='{cleaned}' ACCEPTED=False")
            return "ORG_HOURS"

        temp_data["hours"] = cleaned
        self._update_temp_data(phone, temp_data)
        logger.info(f"[org] STATE=ORG_HOURS INPUT='{cleaned}' ACCEPTED=True")

        # Show summary and confirm
        summary = f"""
🏢 CONFIRMAR CADASTRO:

📍 Nome: {temp_data.get('name', '')}
🏙️ Atuação: {temp_data.get('coverage_area', '')}
🚗 Busca: {'Sim' if temp_data.get('can_pickup', False) else 'Não'}
🕐 Horários: {temp_data.get('hours', '')}

✅ Correto? Responda SIM para confirmar.
❌ Para cancelar, digite CANCELAR."""

        whatsapp_service.send_message(phone, summary)
        return "ORG_CONFIRM"

    def handle_confirm(self, phone: str, message: str) -> str:
        """Handle organization registration confirmation."""
        message_lower = message.lower().strip()

        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        if message_lower in ["sim", "s", "ok", "correto", "✅", "yes"]:
            # Create organization
            temp_data = self._get_temp_data(phone)

            # Get or create user
            user = self.db.query(models.User).filter(models.User.phone == phone).first()
            if not user:
                user = models.User(phone=phone, role=models.UserRole.ORG)
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)

            organization = models.Organization(
                user_id=user.id,
                name=temp_data.get("name", ""),
                phone=phone,
                coverage_area=temp_data.get("coverage_area", ""),
                can_pickup=temp_data.get("can_pickup", False),
                hours=temp_data.get("hours", ""),
                active=True
            )

            self.db.add(organization)
            self.db.commit()
            self.db.refresh(organization)

            # Success message (não volta ao menu automaticamente)
            success_msg = f"""✅ Organização "{organization.name}" cadastrada com sucesso!

🏙️ Região: {organization.coverage_area or 'Não informada'}
🚗 Busca: {"Sim" if organization.can_pickup else "Não"}
🕐 Horários: {organization.hours or 'Não informado'}

🎯 Agora você receberá notificações de doações disponíveis na sua área.
📞 Fique atento ao WhatsApp para oportunidades de retirada.

Digite MENU para voltar ao menu."""

            whatsapp_service.send_message(phone, success_msg)

            # Mantém estado pós-cadastro
            self.menu_flow._update_state(phone, "ORG_COMPLETED", None)
            logger.info(f"[org] completed_flow=ORG phone={phone} org_id={organization.id}")
            return "ORG_COMPLETED"

        else:
            # User wants to edit - go back to name
            whatsapp_service.send_message(
                phone,
                "Vamos refazer o cadastro. Qual o nome da organização?"
            )
            return "ORG_NAME"

    def _is_cancel_command(self, message: str) -> bool:
        """Check if message is a cancel command."""
        message_lower = message.lower().strip()
        return message_lower in ["cancelar", "c", "cancel", "❌"]

    def _cancel_flow(self, phone: str) -> str:
        """Cancel current flow and return to menu."""
        self._clear_temp_data(phone)
        whatsapp_service.send_message(phone, "❌ Cadastro cancelado.")
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


