"""Ortam yapılandırması ve Dependency Injection (Bağımlılık Enjeksiyonu) konteyneri."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from application.use_cases.gorev_durum_degistir import GorevDurumDegistirUseCase
from application.use_cases.gorev_getir import GorevGetirUseCase
from application.use_cases.gorev_guncelle import GorevGuncelleUseCase
from application.use_cases.gorev_listele import GorevListeleUseCase
from application.use_cases.gorev_olustur import GorevOlusturUseCase
from application.use_cases.gorev_sil import GorevSilUseCase
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu
from infrastructure.persistence.in_memory_gorev_repository import (
    InMemoryGorevRepository,
)
from infrastructure.persistence.sqlite_gorev_repository import (
    SqliteGorevRepository,
)

DESTEKLENEN_REPO_TIPLERI: frozenset[str] = frozenset({"sqlite", "memory"})


@dataclass(frozen=True)
class Ayarlar:
    """Ortam değişkenlerinden okunan uygulama yapılandırma ayarları."""

    repo_tipi: str = "sqlite"
    sqlite_db_path: str = "./gorevler.db"

    def __post_init__(self) -> None:
        normalize_tip = self.repo_tipi.strip().lower()
        if normalize_tip not in DESTEKLENEN_REPO_TIPLERI:
            raise ValueError(
                f"Geçersiz REPO_TYPE değeri: '{self.repo_tipi}'. "
                f"Desteklenen değerler: {', '.join(sorted(DESTEKLENEN_REPO_TIPLERI))}."
            )
        object.__setattr__(self, "repo_tipi", normalize_tip)

    @classmethod
    def ortamdan_yukle(cls) -> Ayarlar:
        """İşletim sistemi ortam değişkenlerinden yapılandırmayı okur."""
        return cls(
            repo_tipi=os.getenv("REPO_TYPE", "sqlite"),
            sqlite_db_path=os.getenv("SQLITE_DB_PATH", "./gorevler.db"),
        )

    @property
    def sqlite_url(self) -> str:
        """SQLAlchemy ile uyumlu SQLite bağlantı URL'sini üretir."""
        if self.sqlite_db_path == ":memory:":
            return "sqlite:///:memory:"
        if self.sqlite_db_path.startswith("sqlite://"):
            return self.sqlite_db_path
        posix_yol = Path(self.sqlite_db_path).as_posix()
        return f"sqlite:///{posix_yol}"


class BagimlilikKonteyneri:
    """Seçilen repository adaptörünü kullanım senaryolarına enjekte eden DI konteyneri."""

    def __init__(
        self,
        ayarlar: Optional[Ayarlar] = None,
        repository: Optional[GorevRepositoryArayuzu] = None,
    ) -> None:
        self._ayarlar: Ayarlar = ayarlar if ayarlar is not None else Ayarlar.ortamdan_yukle()
        if repository is not None:
            self._repository: GorevRepositoryArayuzu = repository
            self._repo_tipi: str = (
                "memory"
                if isinstance(repository, InMemoryGorevRepository)
                else self._ayarlar.repo_tipi
            )
        else:
            self._repository = self._repository_olustur(self._ayarlar)
            self._repo_tipi = self._ayarlar.repo_tipi

    @staticmethod
    def _repository_olustur(ayarlar: Ayarlar) -> GorevRepositoryArayuzu:
        """Ayarlar doğrultusunda uygun somut repository implementasyonunu seçer."""
        if ayarlar.repo_tipi == "memory":
            return InMemoryGorevRepository()
        return SqliteGorevRepository(veritabani_url=ayarlar.sqlite_url)

    @property
    def ayarlar(self) -> Ayarlar:
        """Aktif yapılandırma ayarlarını döndürür."""
        return self._ayarlar

    @property
    def repository(self) -> GorevRepositoryArayuzu:
        """Enjekte edilen soyut görev deposu örneğini döndürür."""
        return self._repository

    @property
    def aktif_repo_tipi(self) -> str:
        """Çalışma zamanında aktif olan depo tipini ('sqlite' veya 'memory') döndürür."""
        return self._repo_tipi

    def gorev_olustur_use_case(self) -> GorevOlusturUseCase:
        """GorevOlusturUseCase örneği üretir."""
        return GorevOlusturUseCase(self._repository)

    def gorev_listele_use_case(self) -> GorevListeleUseCase:
        """GorevListeleUseCase örneği üretir."""
        return GorevListeleUseCase(self._repository)

    def gorev_getir_use_case(self) -> GorevGetirUseCase:
        """GorevGetirUseCase örneği üretir."""
        return GorevGetirUseCase(self._repository)

    def gorev_guncelle_use_case(self) -> GorevGuncelleUseCase:
        """GorevGuncelleUseCase örneği üretir."""
        return GorevGuncelleUseCase(self._repository)

    def gorev_durum_degistir_use_case(self) -> GorevDurumDegistirUseCase:
        """GorevDurumDegistirUseCase örneği üretir."""
        return GorevDurumDegistirUseCase(self._repository)

    def gorev_sil_use_case(self) -> GorevSilUseCase:
        """GorevSilUseCase örneği üretir."""
        return GorevSilUseCase(self._repository)

    def kapat(self) -> None:
        """Varsa kalıcı depo kaynaklarını güvenli şekilde serbest bırakır."""
        kapat_metodu = getattr(self._repository, "kapat", None)
        if callable(kapat_metodu):
            kapat_metodu()


_varsayilan_konteyner: Optional[BagimlilikKonteyneri] = None


def konteyneri_getir() -> BagimlilikKonteyneri:
    """Varsayılan uygulama bağımlılık konteynerini tembel olarak oluşturur ve döndürür."""
    global _varsayilan_konteyner
    if _varsayilan_konteyner is None:
        _varsayilan_konteyner = BagimlilikKonteyneri()
    return _varsayilan_konteyner


def konteyneri_sifirla() -> None:
    """Varsayılan konteyneri kapatır ve sıfırlar."""
    global _varsayilan_konteyner
    if _varsayilan_konteyner is not None:
        _varsayilan_konteyner.kapat()
        _varsayilan_konteyner = None
