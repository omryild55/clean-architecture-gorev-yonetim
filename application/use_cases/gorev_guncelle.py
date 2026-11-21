"""Görev bilgilerini güncelleme kullanım senaryosu."""

from __future__ import annotations

from application.dtos.gorev_dto import GorevCikti, GorevGuncelleGirdi
from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevGuncelleUseCase:
    """Mevcut görevin başlık, açıklama, öncelik ve bitiş tarihini günceller."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, girdi: GorevGuncelleGirdi) -> GorevCikti:
        """Görevi yükler, domain kurallarına göre günceller ve depoya kaydeder."""
        gorev = self._repository.id_ile_getir(girdi.gorev_id)
        if gorev is None:
            raise GorevBulunamadiHatasi(girdi.gorev_id)

        gorev.guncelle(
            baslik=girdi.baslik,
            aciklama=girdi.aciklama,
            oncelik=girdi.oncelik,
            bitis_tarihi=girdi.bitis_tarihi,
            bitis_tarihini_temizle=girdi.bitis_tarihini_temizle,
        )
        guncellenen_gorev = self._repository.guncelle(gorev)
        return GorevCikti.varliktan_olustur(guncellenen_gorev)
