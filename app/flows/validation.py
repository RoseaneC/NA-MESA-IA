from __future__ import annotations

from typing import Set


_RESERVED: Set[str] = {"menu", "voltar", "reiniciar", "m"}
_MENU_OPTIONS: Set[str] = {"1", "2", "3", "4"}


def is_menu_option(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    return cleaned in _MENU_OPTIONS


def is_reserved(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    return cleaned in _RESERVED


def is_valid_name(text: str) -> bool:
    cleaned = (text or "").strip()
    if len(cleaned) < 3:
        return False
    if cleaned.isdigit():
        return False
    lower = cleaned.lower()
    if lower in _RESERVED:
        return False
    if lower in _MENU_OPTIONS:
        return False
    return True


def is_yes(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    return cleaned in {"sim", "s", "yes", "✅", "ok", "correto"}


def is_no(text: str) -> bool:
    cleaned = (text or "").strip().lower()
    return cleaned in {"nao", "não", "n", "❌", "nao consigo", "não consigo", "recusar"}

