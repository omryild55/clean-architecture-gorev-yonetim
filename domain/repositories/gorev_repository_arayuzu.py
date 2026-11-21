"""Görev veri erişimi için soyut depo arayüzü (Dependency Inversion Principle)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from domain.entities.gorev import Gorev
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


class GorevRepositoryArayuzu(ABC):
    """Dış dünya kalıcılık adaptörlerinin uygulaması gereken depo sözleşmesi."""

    @abstractmethod
    def kaydet(self, gorev: Gorev) -> Gorev:
        """Yeni bir görevi kalıcı depoya ekler ve kaydedilen varlığı döndürür."""

    @abstractmethod
    def id_ile_getir(self, gorev_id: str) -> Optional[Gorev]:
        """Verilen kimliğe sahip görevi döndürür; bulunamazsa None döndürür."""

    @abstractmethod
    def tumunu_listele(
        self,
        durum: Optional[GorevDurumu] = None,
        oncelik: Optional[GorevOnceligi] = None,
        arama_metni: Optional[str] = None,
    ) -> list[Gorev]:
        """Filtre ölçütlerine uyan tüm görevleri listeler."""

    @abstractmethod
    def guncelle(self, gorev: Gorev) -> Gorev:
        """Mevcut bir görevin güncel durumunu kalıcı depoya yansıtır."""

    @abstractmethod
    def sil(self, gorev_id: str) -> bool:
        """Verilen kimliğe sahip görevi siler; işlem başarılıysa True döndürür."""
