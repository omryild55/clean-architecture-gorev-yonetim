"""Kalıcılık (Persistence) katmanı depo adaptörleri."""

from infrastructure.persistence.in_memory_gorev_repository import (
    InMemoryGorevRepository,
)
from infrastructure.persistence.sqlite_gorev_repository import (
    SqliteGorevRepository,
)

__all__ = ["InMemoryGorevRepository", "SqliteGorevRepository"]
