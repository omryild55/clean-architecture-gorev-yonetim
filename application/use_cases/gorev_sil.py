"""Görev silme kullanım senaryosu."""

from __future__ import annotations

from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevSilUseCase:
    """Silme koruma kurallarını doğrulayarak görevi kalıcı depodan kaldırır."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, gorev_id: str) -> None:
        """Görevi bulur, silinebilirlik kuralını doğrular ve siler."""
        gorev = self._repository.id_ile_getir(gorev_id)
        if gorev is None:
            raise GorevBulunamadiHatasi(gorev_id)

        gorev.silinebilir_mi_dogrula()
        self._repository.sil(gorev_id)
