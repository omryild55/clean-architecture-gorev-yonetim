"""Yeni görev oluşturma kullanım senaryosu."""

from __future__ import annotations

from application.dtos.gorev_dto import GorevCikti, GorevOlusturGirdi
from domain.entities.gorev import Gorev
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevOlusturUseCase:
    """Yeni bir görevin domain kurallarına göre oluşturulup kaydedilmesini yönetir."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, girdi: GorevOlusturGirdi) -> GorevCikti:
        """Girdi verilerinden yeni görev oluşturur, depolar ve çıktı DTO'su döndürür."""
        yeni_gorev = Gorev.olustur(
            baslik=girdi.baslik,
            aciklama=girdi.aciklama,
            oncelik=girdi.oncelik,
            bitis_tarihi=girdi.bitis_tarihi,
        )
        kaydedilen_gorev = self._repository.kaydet(yeni_gorev)
        return GorevCikti.varliktan_olustur(kaydedilen_gorev)
