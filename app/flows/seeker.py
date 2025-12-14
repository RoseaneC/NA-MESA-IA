from sqlalchemy.orm import Session
from typing import List

from ..db import models
from ..core.logging import logger
from ..services.whatsapp import whatsapp_service
from ..services.matching import MatchingService
from ..services.normalization import normalize_neighborhood
from .menu import MenuFlow
from .validation import is_menu_option, is_reserved


class SeekerFlow:
    def __init__(self, db: Session):
        self.db = db
        self.menu_flow = MenuFlow(db)
        self.matching_service = MatchingService(db)
        self.default_options = [
            {
                "name": "Cozinha Solidária Rocinha",
                "phone": "+55 21 99999-1111",
                "coverage": "Rocinha",
                "hours": "Seg a Sex 11h-20h",
            },
            {
                "name": "ONG Esperança",
                "phone": "+55 21 98888-2222",
                "coverage": "Rocinha, Vidigal",
                "hours": "Diariamente 10h-19h",
            },
            {
                "name": "Cozinha Popular",
                "phone": "+55 21 97777-3333",
                "coverage": "Zona Sul",
                "hours": "Seg a Sáb 12h-18h",
            },
        ]

    def handle_location(self, phone: str, message: str) -> str:
        """Handle location input and provide food options."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 3:
            whatsapp_service.send_message(
                phone,
                "Informe o bairro/região (ex: Centro, Rocinha, Vila Mariana)."
            )
            logger.info(f"[seeker] STATE=SEEK_LOCATION INPUT='{cleaned}' ACCEPTED=False")
            return "SEEK_LOCATION"

        neighborhood = normalize_neighborhood(cleaned)
        logger.info(f"[seeker] STATE=SEEK_LOCATION INPUT='{cleaned}' ACCEPTED=True")

        # Get active distributions first (higher priority)
        active_distributions = self.matching_service.get_active_distributions(neighborhood)

        # Get organizations in the area
        organizations = self._get_organizations_in_area(neighborhood)

        options_rendered = []

        if active_distributions:
            for dist in active_distributions[:3]:
                options_rendered.append(
                    f"🚚 {dist.location} | {dist.food_type} | {dist.qty} | Até {dist.expires_at.strftime('%H:%M') if hasattr(dist.expires_at, 'strftime') else dist.expires_at}"
                )

        if organizations:
            for org in organizations[:3]:
                options_rendered.append(
                    f"🏢 {org.name} | {org.phone} | {org.coverage_area or 'Região não informada'} | {org.hours or 'Horário não informado'}"
                )

        if not options_rendered:
            for opt in self.default_options[:3]:
                options_rendered.append(
                    f"🏢 {opt['name']} | {opt['phone']} | {opt['coverage']} | {opt['hours']}"
                )

        response_parts = ["🍽️ OPÇÕES DE COMIDA PRÓXIMAS:"]
        response_parts.extend([f"- {opt}" for opt in options_rendered])
        response_parts.append("\n⚠️ IMPORTANTE:\n• Não prometemos comida, apenas orientamos opções disponíveis\n• Entre em contato diretamente com os locais\n• Digite MENU para voltar")

        # Update user role
        self._update_user_role(phone, models.UserRole.SEEKER)

        # Send response
        full_response = "\n".join(response_parts)
        whatsapp_service.send_message(phone, full_response)

        # Mantém estado pós-resposta
        self.menu_flow._update_state(phone, "SEEK_COMPLETED", None)
        logger.info(f"[seeker] completed_flow=SEEK phone={phone} options={len(options_rendered)}")
        return "SEEK_COMPLETED"

    def handle_item(self, phone: str, message: str) -> str:
        """Ask what the user needs."""
        if self._is_cancel_command(message):
            return self._cancel_flow(phone)

        cleaned = (message or "").strip()
        if is_menu_option(cleaned) or is_reserved(cleaned) or len(cleaned) < 2:
            whatsapp_service.send_message(
                phone,
                "O que você precisa? (ex: marmita, cesta básica)."
            )
            logger.info(f"[seeker] STATE=SEEK_ITEM INPUT='{cleaned}' ACCEPTED=False")
            return "SEEK_ITEM"

        whatsapp_service.send_message(
            phone,
            "Qual bairro/região você está? (ex: Centro, Rocinha)."
        )
        self.menu_flow._update_state(phone, "SEEK_LOCATION")
        logger.info(f"[seeker] STATE=SEEK_ITEM INPUT='{cleaned}' ACCEPTED=True")
        return "SEEK_LOCATION"

    def _get_organizations_in_area(self, neighborhood: str) -> List[models.Organization]:
        """Get organizations that cover the given neighborhood."""
        organizations = self.db.query(models.Organization).filter(
            models.Organization.active == True
        ).all()

        matching_orgs = []
        for org in organizations:
            if org.coverage_area:
                org_areas = [normalize_neighborhood(area.strip())
                           for area in org.coverage_area.split(',')]
                if neighborhood in org_areas:
                    matching_orgs.append(org)

        return matching_orgs

    def _is_cancel_command(self, message: str) -> bool:
        """Check if message is a cancel command."""
        message_lower = message.lower().strip()
        return message_lower in ["cancelar", "c", "cancel", "❌"]

    def _cancel_flow(self, phone: str) -> str:
        """Cancel current flow and return to menu."""
        self._clear_temp_data(phone)
        whatsapp_service.send_message(phone, "❌ Busca cancelada.")
        self.menu_flow.show_menu(phone)
        return "MENU"

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


