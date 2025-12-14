import re
import logging
from sqlalchemy.orm import Session

from ..db import models
from ..services.whatsapp import whatsapp_service
from ..services.matching import MatchingService
from .menu import MenuFlow
from .state_store import (
    load_state,
    merge_temp_and_advance,
    set_state_and_temp,
    get_temp,
)

logger = logging.getLogger("uvicorn.error")

YES_RE = re.compile(r"^(sim|s|confirmar|confirmo|ok|✅)$", re.I)
NO_RE = re.compile(r"^(nao|não|n|cancelar|cancela|❌)$", re.I)
EDIT_RE = re.compile(r"^(editar|voltar)$", re.I)


def _log_persist(db: Session, phone: str, label: str) -> None:
    row = load_state(db, phone)
    logger.info(
        f"[donate] {label} phone={phone} state={row.state} "
        f"temp={get_temp(db, phone)} raw_temp_type={type(row.temp_json).__name__}"
    )


class DonateFlow:
    def __init__(self, db: Session):
        self.db = db
        self.menu_flow = MenuFlow(db)
        self.matching_service = MatchingService(db)

    def handle_food_type(self, phone: str, message: str) -> str:
        """Handle food type input."""
        incoming = (message or "").strip()
        if self._is_cancel_command(incoming):
            return self._cancel_flow(phone)

        _log_persist(self.db, phone, "before FOOD_TYPE")
        merge_temp_and_advance(
            self.db,
            phone,
            patch={"food_type": incoming},
            next_state="DONATE_QTY",
        )
        _log_persist(self.db, phone, "after FOOD_TYPE")

        whatsapp_service.send_message(
            phone,
            "📦 Qual a quantidade aproximada?\n\nExemplos: 5kg, 10 porções, 3 marmitas"
        )
        return "DONATE_QTY"

    def handle_quantity(self, phone: str, message: str) -> str:
        """Handle quantity input."""
        incoming = (message or "").strip()
        if self._is_cancel_command(incoming):
            return self._cancel_flow(phone)

        _log_persist(self.db, phone, "before QTY")
        merge_temp_and_advance(
            self.db,
            phone,
            patch={"qty": incoming},
            next_state="DONATE_EXPIRES",
        )
        _log_persist(self.db, phone, "after QTY")

        whatsapp_service.send_message(
            phone,
            "⏰ Até que horas está boa para retirada?\n\nExemplos: 18h, hoje até 20h, amanhã de manhã"
        )
        return "DONATE_EXPIRES"

    def handle_expires_at(self, phone: str, message: str) -> str:
        """Handle expiration time input."""
        incoming = (message or "").strip()
        if self._is_cancel_command(incoming):
            return self._cancel_flow(phone)

        _log_persist(self.db, phone, "before EXPIRES")
        merge_temp_and_advance(
            self.db,
            phone,
            patch={"expires_at": incoming},
            next_state="DONATE_LOCATION",
        )
        _log_persist(self.db, phone, "after EXPIRES")

        whatsapp_service.send_message(
            phone,
            "🏠 Qual o bairro/local para retirada?\n\nExemplo: Centro, Vila Mariana, Rua das Flores 123"
        )
        return "DONATE_LOCATION"

    def handle_location(self, phone: str, message: str) -> str:
        """Handle location input and proceed to confirm."""
        incoming = (message or "").strip()
        if self._is_cancel_command(incoming):
            return self._cancel_flow(phone)

        _log_persist(self.db, phone, "before LOCATION")
        merge_temp_and_advance(
            self.db,
            phone,
            patch={"location": incoming},
            next_state="DONATE_CONFIRM",
        )
        _log_persist(self.db, phone, "after LOCATION")

        temp_data = get_temp(self.db, phone)
        summary = f"""
📋 CONFIRMAR DOAÇÃO:

🍽️  Comida: {temp_data.get('food_type', '')}
📦 Quantidade: {temp_data.get('qty', '')}
⏰ Válido até: {temp_data.get('expires_at', '')}
🏠 Local: {temp_data.get('location', '')}

✅ Correto? Responda SIM ou edite os dados.
❌ Para cancelar, digite CANCELAR."""

        whatsapp_service.send_message(phone, summary)
        return "DONATE_CONFIRM"

    def handle_confirm(self, phone: str, message: str) -> str:
        """Handle donation confirmation."""
        incoming = (message or "").strip()
        text_lower = incoming.lower()
        _log_persist(self.db, phone, "before CONFIRM")
        temp_data = get_temp(self.db, phone)
        logger.info(
            f"[donate] confirm step phone={phone} "
            f"food_type={temp_data.get('food_type','')} "
            f"qty={temp_data.get('qty','')} "
            f"expires_at={temp_data.get('expires_at','')} "
            f"location={temp_data.get('location','')}"
        )

        if self._is_cancel_command(incoming):
            result = self._cancel_flow(phone)
            _log_persist(self.db, phone, "cancelled CONFIRM")
            return result

        if YES_RE.match(text_lower):
            logger.info(
                f"[donate] creating donation phone={phone} "
                f"food_type={temp_data.get('food_type','')} "
                f"qty={temp_data.get('qty','')} "
                f"expires_at={temp_data.get('expires_at','')} "
                f"location={temp_data.get('location','')}"
            )

            donation = models.Donation(
                donor_phone=phone,
                food_type=temp_data.get("food_type", ""),
                qty=temp_data.get("qty", ""),
                expires_at=temp_data.get("expires_at", ""),
                location=temp_data.get("location", ""),
                status=models.DonationStatus.PENDING
            )

            self.db.add(donation)
            self.db.commit()
            self.db.refresh(donation)

            # Estado pós-doação: mantém o usuário no fluxo
            set_state_and_temp(self.db, phone, state="DONATE_POST_MATCH", clear_temp=True)
            _log_persist(self.db, phone, "confirmed YES -> DONATE_POST_MATCH")

            # Update user role if needed
            self._update_user_role(phone, models.UserRole.DONOR)

            # Matching e sugestões de entrega
            match = self.matching_service.match_donation(donation)
            recipients = self.matching_service.find_best_recipients(donation, limit=3)

            success_msg = "✅ Doação cadastrada com sucesso!"
            if match:
                success_msg += "\n\n🔍 Procurando organizações próximas para retirada..."
            else:
                success_msg += "\n\n📝 Estamos buscando um ponto de entrega próximo."

            whatsapp_service.send_message(phone, success_msg)

            delivery_msg = self._format_pickup_options(recipients)
            whatsapp_service.send_message(phone, delivery_msg)

            return "DONATE_POST_MATCH"

        if NO_RE.match(text_lower):
            set_state_and_temp(self.db, phone, state="MENU", clear_temp=True)
            _log_persist(self.db, phone, "confirmed NO")
            whatsapp_service.send_message(phone, "❌ Doação cancelada.")
            self.menu_flow.show_menu(phone)
            return "MENU"

        if EDIT_RE.match(text_lower):
            set_state_and_temp(self.db, phone, state="DONATE_FOOD_TYPE", clear_temp=True)
            _log_persist(self.db, phone, "restart after EDIT")
            whatsapp_service.send_message(
                phone,
                "Vamos refazer a doação. Qual o tipo de comida?"
            )
            return "DONATE_FOOD_TYPE"

        # Não entendido: permanece em CONFIRM mantendo temp
        set_state_and_temp(self.db, phone, state="DONATE_CONFIRM", temp=None)
        _log_persist(self.db, phone, "repeat CONFIRM invalid")
        whatsapp_service.send_message(
            phone,
            "Não entendi. Responda SIM para confirmar, NÃO para cancelar ou EDITAR para refazer."
        )
        return "DONATE_CONFIRM"

    def _format_pickup_options(self, recipients):
        if recipients:
            parts = ["📍 Você pode entregar sua doação em uma das opções abaixo:"]
            for org in recipients:
                parts.append(
                    f"\n🏢 {org.name}\n📞 {org.phone}\n🏙️ {org.coverage_area or 'Cobertura não informada'}"
                    f"\n🚗 {'Retira no local' if org.can_pickup else 'Retirada no ponto informado'}"
                    f"\n🕐 {org.hours or 'Horário não informado'}"
                )
            parts.append("\nSe precisar de mais opções, digite 'menu'.")
            return "\n".join(parts)

        return (
            "⚠️ Ainda não encontramos uma organização cadastrada próxima.\n"
            "Um voluntário pode entrar em contato. Se precisar voltar ao menu, digite 'menu'."
        )

    def _is_cancel_command(self, message: str) -> bool:
        """Check if message is a cancel command."""
        message_lower = (message or "").lower().strip()
        return message_lower in ["cancelar", "c", "cancel", "❌"]

    def _cancel_flow(self, phone: str) -> str:
        """Cancel current flow and return to menu."""
        set_state_and_temp(self.db, phone, state="MENU", clear_temp=True)
        whatsapp_service.send_message(phone, "❌ Doação cancelada.")
        self.menu_flow.show_menu(phone)
        return "MENU"

    def _update_user_role(self, phone: str, role: str) -> None:
        """Update or create user with role."""
        user = self.db.query(models.User).filter(models.User.phone == phone).first()
        if user:
            user.role = role
        else:
            user = models.User(phone=phone, role=role)
            self.db.add(user)
        self.db.commit()
