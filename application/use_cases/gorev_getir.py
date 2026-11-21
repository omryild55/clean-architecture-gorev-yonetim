"""Tekil görev getirme kullanım senaryosu."""

from __future__ import annotations

from application.dtos.gorev_dto import GorevCikti
from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevGetirUseCase:
    """Kimliği verilen tekil bir görevin getirilmesini yönetir."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, gorev_id: str) -> GorevCikti:
        """Görevi kimliğe göre bulur; yoksa GorevBulunamadiHatasi fırlatır."""
        gorev = self._repository.id_ile_getir(gorev_id)
        if gorev is None:
            raise GorevBulunamadiHatasi(gorev_id)
        return GorevCikti.varliktan_olustur(gorev)
