import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./vexia.db"
    auto_create_db: bool = False

    # WhatsApp Cloud API
    whatsapp_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    verify_token: str = "vexia_verify_token_default"
    whatsapp_verify_token: Optional[str] = None

    # OpenAI
    openai_api_key: Optional[str] = None

    # Application
    debug: bool = False
    log_level: str = "INFO"
    node_send_url: str = "http://127.0.0.1:3000/send"

    # Environment
    environment: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
