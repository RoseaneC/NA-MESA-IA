import logging
import sys
from typing import Optional

from .config import settings


def setup_logging(level: Optional[str] = None) -> None:
    """Configure structured logging for the application."""

    if level is None:
        level = settings.log_level

    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Create logger for this application
    logger = logging.getLogger("vexia")
    logger.setLevel(numeric_level)

    # Avoid duplicate logs
    logger.propagate = False

    return logger


# Global logger instance
logger = setup_logging()


