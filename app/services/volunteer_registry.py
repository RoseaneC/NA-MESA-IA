"""Registro simples em memória para voluntários (uso demo)."""

from typing import List, Dict

_REGISTRY: List[Dict[str, str]] = []


def add_volunteer(entry: Dict[str, str]) -> None:
    _REGISTRY.append(entry)


def list_volunteers() -> List[Dict[str, str]]:
    return list(_REGISTRY)

