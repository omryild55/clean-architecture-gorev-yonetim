"""Görev durumunu değiştirme kullanım senaryosu."""

from __future__ import annotations

from application.dtos.gorev_dto import GorevCikti, GorevDurumDegistirGirdi
from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevDurumDegistirUseCase:
    """Görev durumunu durum makinesi kurallarına göre günceller."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, girdi: GorevDurumDegistirGirdi) -> GorevCikti:
        """Görevi yükler, hedef duruma geçişi doğrular ve yeni durumu kaydeder."""
        gorev = self._repository.id_ile_getir(girdi.gorev_id)
        if gorev is None:
            raise GorevBulunamadiHatasi(girdi.gorev_id)

        gorev.durum_degistir(girdi.yeni_durum)
        guncellenen_gorev = self._repository.guncelle(gorev)
        return GorevCikti.varliktan_olustur(guncellenen_gorev)
