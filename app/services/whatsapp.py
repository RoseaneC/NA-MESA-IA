import requests
from typing import Callable, Optional

from ..core.config import settings
from ..core.logging import logger


class WhatsAppService:
    def __init__(self):
        self.token = settings.whatsapp_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.base_url = "https://graph.facebook.com/v18.0"
        self._sender_override: Optional[Callable[[str, str], bool]] = None

    def set_sender_override(
        self, sender: Optional[Callable[[str, str], bool]]
    ) -> Optional[Callable[[str, str], bool]]:
        """Temporarily override the send implementation (useful for captures/tests)."""
        previous = self._sender_override
        self._sender_override = sender
        return previous

    def send_message(self, phone: str, text: str) -> bool:
        """Send a WhatsApp message to a phone number."""
        if self._sender_override:
            try:
                return bool(self._sender_override(phone, text))
            except Exception as exc:
                logger.error(f"Sender override failed for {phone}: {exc}")
                return False

        if not self.token or not self.phone_number_id:
            logger.warning("WhatsApp credentials not configured, skipping message send")
            return False

        url = f"{self.base_url}/{self.phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {
                "body": text
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            logger.info(f"WhatsApp message sent to {phone}: {text[:50]}...")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp message to {phone}: {e}")
            return False

    def verify_webhook(self, hub_verify_token: str, hub_challenge: str, hub_mode: str) -> Optional[str]:
        """Verify WhatsApp webhook."""
        if hub_mode == "subscribe" and hub_verify_token == settings.verify_token:
            logger.info("WhatsApp webhook verified successfully")
            return hub_challenge

        logger.warning("WhatsApp webhook verification failed")
        return None


# Global instance
whatsapp_service = WhatsAppService()


