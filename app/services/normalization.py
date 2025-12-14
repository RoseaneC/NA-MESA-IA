import re
import unicodedata
from typing import Optional


def normalize_neighborhood(text: str) -> str:
    """Normalize neighborhood name: lowercase, remove accents, strip whitespace."""
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower().strip()

    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

    # Remove special characters and extra spaces
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def normalize_phone(phone: str) -> Optional[str]:
    """Normalize phone number to international format."""
    if not phone:
        return None

    # Remove all non-numeric characters
    digits = re.sub(r'\D', '', phone)

    # Handle Brazilian phone numbers
    if len(digits) == 11:  # Mobile with area code
        return f"+55{digits}"
    elif len(digits) == 10:  # Landline with area code
        return f"+55{digits}"
    elif len(digits) == 13 and digits.startswith('55'):  # Already international
        return f"+{digits}"

    # Return as-is if we can't normalize
    return phone


