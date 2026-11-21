"""Pytest ortak fikstürleri (hem In-Memory hem de SQLite için parametreli)."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu
from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri
from infrastructure.persistence.in_memory_gorev_repository import (
    InMemoryGorevRepository,
)
from infrastructure.persistence.sqlite_gorev_repository import (
    SqliteGorevRepository,
)
from main import uygulama_olustur


@pytest.fixture(params=["memory", "sqlite"], scope="function")
def depo_tipi(request: pytest.FixtureRequest) -> str:
    """Tüm entegrasyon testlerini hem memory hem sqlite üzerinde koşturur."""
    return str(request.param)


@pytest.fixture(scope="function")
def repository(
    depo_tipi: str,
    tmp_path: Path,
) -> Generator[GorevRepositoryArayuzu, None, None]:
    """İstenen depo tipine göre izole bir repository örneği sağlar."""
    if depo_tipi == "memory":
        depo = InMemoryGorevRepository()
        yield depo
        depo.temizle()
        return

    veritabani_dosyasi = tmp_path / "test_gorevler.db"
    sqlite_depo = SqliteGorevRepository(
        veritabani_url=f"sqlite:///{veritabani_dosyasi.as_posix()}"
    )
    try:
        yield sqlite_depo
    finally:
        sqlite_depo.kapat()


@pytest.fixture(scope="function")
def api_istemcisi(
    depo_tipi: str,
    tmp_path: Path,
) -> Generator[tuple[TestClient, str], None, None]:
    """Seçili repository ile yapılandırılmış izole FastAPI TestClient döndürür."""
    if depo_tipi == "memory":
        ayarlar = Ayarlar(repo_tipi="memory")
    else:
        veritabani_dosyasi = tmp_path / "api_test_gorevler.db"
        ayarlar = Ayarlar(
            repo_tipi="sqlite",
            sqlite_db_path=str(veritabani_dosyasi),
        )

    konteyner = BagimlilikKonteyneri(ayarlar=ayarlar)
    app = uygulama_olustur(konteyner=konteyner)
    with TestClient(app) as istemci:
        yield istemci, depo_tipi
