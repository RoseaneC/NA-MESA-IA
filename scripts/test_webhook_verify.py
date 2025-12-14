"""
Teste rápido para validar a verificação do webhook do WhatsApp.

Pré-requisitos:
- Servidor rodando localmente (uvicorn/main).
- Biblioteca `requests` já está listada em requirements.

Use:
    python scripts/test_webhook_verify.py
    WEBHOOK_VERIFY_URL="http://localhost:8000/webhook/whatsapp" WHATSAPP_VERIFY_TOKEN="meu_token" python scripts/test_webhook_verify.py
"""

import os

import requests


BASE_URL = os.getenv("WEBHOOK_VERIFY_URL", "http://localhost:8000/webhook/whatsapp")
DEFAULT_TOKEN = "vexia_verify_token_default"


def main() -> None:
    expected_token = (
        os.getenv("WHATSAPP_VERIFY_TOKEN")
        or os.getenv("VERIFY_TOKEN")
        or DEFAULT_TOKEN
    )
    challenge = "123456"

    valid_params = {
        "hub.mode": "subscribe",
        "hub.verify_token": expected_token,
        "hub.challenge": challenge,
    }
    invalid_params = {**valid_params, "hub.verify_token": "token_errado"}

    print(f"### Teste válido -> {BASE_URL}")
    valid_resp = requests.get(BASE_URL, params=valid_params)
    print(f"Status: {valid_resp.status_code} | Body: {valid_resp.text}")

    print(f"\n### Teste sem params (200 esperado) -> {BASE_URL}")
    empty_resp = requests.get(BASE_URL)
    print(f"Status: {empty_resp.status_code} | Body: {empty_resp.text}")

    print(f"\n### Teste inválido (403 esperado) -> {BASE_URL}")
    invalid_resp = requests.get(BASE_URL, params=invalid_params)
    print(f"Status: {invalid_resp.status_code} | Body: {invalid_resp.text}")


if __name__ == "__main__":
    main()

