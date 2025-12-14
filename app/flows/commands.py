from typing import Optional

from ..services.whatsapp import whatsapp_service
from ..core.logging import logger


MENU_NUMBERS = {"1", "2", "3", "4"}


def handle_global_commands(phone: str, text_lower: str, state: str) -> Optional[str]:
    """Handle global commands like reiniciar/cancel/menu. Returns next_state or None."""
    # Reiniciar: sempre volta ao menu
    if text_lower in {"reiniciar"}:
        whatsapp_service.send_message(
            phone, "Reiniciando. Exibindo o menu principal."
        )
        return "MENU"
    return None


def handle_menu_number_outside_menu(phone: str, text: str, state: str) -> bool:
    """Bloqueia números 1-4 fora do MENU e orienta o usuário. Retorna True se tratado."""
    cleaned = (text or "").strip()
    if cleaned not in MENU_NUMBERS:
        return False

    prefix_msg = None
    upper_state = (state or "").upper()
    if upper_state.startswith("ORG_"):
        prefix_msg = (
            "Você está cadastrando uma ONG. Digite o NOME do projeto (ex: Cozinha Solidária X).\n"
            "Para sair, digite CANCELAR. Para voltar ao menu, digite MENU."
        )
    elif upper_state.startswith("SEEK"):
        prefix_msg = (
            "Você está pedindo ajuda. Informe o bairro/região (ex: Centro, Rocinha).\n"
            "Para sair, digite CANCELAR. Para voltar ao menu, digite MENU."
        )
    elif upper_state.startswith("VOLUNTEER_"):
        prefix_msg = (
            "Você está se cadastrando como voluntário. Informe o dado solicitado.\n"
            "Para sair, digite CANCELAR. Para voltar ao menu, digite MENU."
        )

    if prefix_msg:
        logger.info(
            f"[global] STATE={state} INPUT='{cleaned}' action=blocked_menu_number"
        )
        whatsapp_service.send_message(phone, prefix_msg)
        return True

    return False

