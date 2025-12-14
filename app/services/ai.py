import json
import re
from typing import Dict, Any, Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..core.config import settings
from ..core.logging import logger


class AIService:
    def __init__(self):
        self.client = None
        if OPENAI_AVAILABLE and settings.openai_api_key:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def extract_intent_and_fields(self, message: str) -> Dict[str, Any]:
        """
        Extract intent and fields from user message using AI or fallback heuristics.

        Returns:
            {
                "intent": "donate|org|seek|volunteer|unknown",
                "food_type": str,
                "qty": str,
                "expires_at": str,
                "location": str
            }
        """
        if self.client:
            return self._extract_with_ai(message)
        else:
            return self._extract_with_heuristics(message)

    def _extract_with_ai(self, message: str) -> Dict[str, Any]:
        """Extract using OpenAI API."""
        prompt = f"""
        Analyze this WhatsApp message in Portuguese and extract structured information.
        Focus on food donation/sharing context.

        Message: "{message}"

        Return ONLY a valid JSON object with this exact structure:
        {{
            "intent": "donate|org|seek|volunteer|unknown",
            "food_type": "",
            "qty": "",
            "expires_at": "",
            "location": ""
        }}

        Intent meanings:
        - donate: user wants to donate food
        - org: user represents an organization/ONG
        - seek: user needs food
        - volunteer: user wants to distribute food now
        - unknown: unclear intent

        Extract food_type, qty, expires_at, location only if mentioned.
        Never invent information. Leave fields empty if not present.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1
            )

            result_text = response.choices[0].message.content.strip()

            # Try to parse JSON
            if result_text.startswith('{') and result_text.endswith('}'):
                result = json.loads(result_text)
                logger.info(f"AI extracted: {result}")
                return result
            else:
                logger.warning(f"AI returned invalid JSON: {result_text}")
                return self._extract_with_heuristics(message)

        except Exception as e:
            logger.error(f"AI extraction failed: {e}")
            return self._extract_with_heuristics(message)

    def _extract_with_heuristics(self, message: str) -> Dict[str, Any]:
        """Fallback extraction using simple heuristics."""
        message_lower = message.lower().strip()

        # Default result
        result = {
            "intent": "unknown",
            "food_type": "",
            "qty": "",
            "expires_at": "",
            "location": ""
        }

        # Simple intent detection
        if any(word in message_lower for word in ["doar", "doação", "sobra", "resta", "tenho comida"]):
            result["intent"] = "donate"
        elif any(word in message_lower for word in ["ong", "organização", "projeto social", "instituição"]):
            result["intent"] = "org"
        elif any(word in message_lower for word in ["preciso", "fome", "comida", "busco", "procurando"]):
            result["intent"] = "seek"
        elif any(word in message_lower for word in ["voluntário", "distribuir", "entregar", "estou na rua", "agora"]):
            result["intent"] = "volunteer"

        # Extract common patterns
        # Food types
        food_patterns = [
            r"(?:tipo|comida|alimento)[:\s]*([^\n,.]+)",
            r"(?:doar|tenho)[:\s]*([^\n,.]+)"
        ]
        for pattern in food_patterns:
            match = re.search(pattern, message_lower)
            if match:
                result["food_type"] = match.group(1).strip()
                break

        # Quantity
        qty_patterns = [
            r"(?:quantidade|qtd|qtde)[:\s]*([^\n,.]+)",
            r"(\d+\s*(?:kg|quilo|porção|prato|pessoa|unidade))"
        ]
        for pattern in qty_patterns:
            match = re.search(pattern, message_lower)
            if match:
                result["qty"] = match.group(1).strip()
                break

        # Location
        location_patterns = [
            r"(?:local|localização|bairro|lugar|endereço)[:\s]*([^\n,.]+)",
            r"(?:em|no|na)\s+([^\n,.]+)"
        ]
        for pattern in location_patterns:
            match = re.search(pattern, message_lower)
            if match:
                result["location"] = match.group(1).strip()
                break

        # Expires at
        expires_patterns = [
            r"(?:até|válido|expira|vence)[:\s]*([^\n,.]+)",
            r"(\d+[:\d]*\s*(?:h|hora))"
        ]
        for pattern in expires_patterns:
            match = re.search(pattern, message_lower)
            if match:
                result["expires_at"] = match.group(1).strip()
                break

        logger.info(f"Heuristic extracted: {result}")
        return result


# Global instance
ai_service = AIService()


