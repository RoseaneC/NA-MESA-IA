"""
Testes rápidos de conversa para fluxos DOAR e ONG.

Uso:
    BASE_URL=http://localhost:8000 python scripts/test_conversations.py

Os testes enviam para o endpoint /webhook (bridge FastAPI).
"""

import os
import time
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")


def send(numero: str, mensagem: str):
    resp = requests.post(
        f"{BASE_URL}/webhook",
        json={"numero": numero, "mensagem": mensagem},
        timeout=5,
    )
    return resp


def test_doar_flow():
    numero = "5511999999999@c.us"
    steps = ["1", "Arroz", "5kg", "hoje 18h", "Centro", "SIM"]
    for step in steps:
        send(numero, step)
        time.sleep(0.2)
    print(">> Fluxo DOAR enviado.")


def test_ong_flow():
    numero = "5511888888888@c.us"
    steps = ["2", "Cozinha Wolly", "Rocinha", "SIM", "Seg a sex 8h-18h", "SIM"]
    for step in steps:
        send(numero, step)
        time.sleep(0.2)
    print(">> Fluxo ONG enviado.")


if __name__ == "__main__":
    test_doar_flow()
    test_ong_flow()
    print("OK - testes enviados. Verifique respostas no backend/logs.")

