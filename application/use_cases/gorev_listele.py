"""Görevleri filtreleyerek listeleme kullanım senaryosu."""

from __future__ import annotations

from typing import Optional

from application.dtos.gorev_dto import GorevCikti, GorevFiltreGirdi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu


class GorevListeleUseCase:
    """Görevlerin durum, öncelik ve arama metnine göre listelenmesini yönetir."""

    def __init__(self, gorev_repository: GorevRepositoryArayuzu) -> None:
        self._repository: GorevRepositoryArayuzu = gorev_repository

    def calistir(self, filtre: Optional[GorevFiltreGirdi] = None) -> list[GorevCikti]:
        """Filtre ölçütlerine uyan görevleri getirir ve çıktı listesine dönüştürür."""
        etkin_filtre = filtre if filtre is not None else GorevFiltreGirdi()
        gorevler = self._repository.tumunu_listele(
            durum=etkin_filtre.durum,
            oncelik=etkin_filtre.oncelik,
            arama_metni=etkin_filtre.arama_metni,
        )
        return [GorevCikti.varliktan_olustur(gorev) for gorev in gorevler]
