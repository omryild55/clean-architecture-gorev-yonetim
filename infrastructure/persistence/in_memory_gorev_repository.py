"""Domain depo sözleşmesini uygulayan bellek içi (In-Memory) adaptör."""

from __future__ import annotations

from threading import RLock
from typing import Optional

from domain.entities.gorev import Gorev
from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


class InMemoryGorevRepository(GorevRepositoryArayuzu):
    """İş parçacığı güvenli (thread-safe) bellek içi görev deposu."""

    def __init__(self) -> None:
        self._gorevler: dict[str, Gorev] = {}
        self._kilit: RLock = RLock()

    def kaydet(self, gorev: Gorev) -> Gorev:
        """Yeni görevi bellek içi sözlüğe ekler ve izole kopyasını döndürür."""
        with self._kilit:
            self._gorevler[gorev.id] = gorev.kopyala()
            return self._gorevler[gorev.id].kopyala()

    def id_ile_getir(self, gorev_id: str) -> Optional[Gorev]:
        """Kimliğe göre görevi arar; bulunursa izole kopyasını döndürür."""
        with self._kilit:
            kayit = self._gorevler.get(gorev_id)
            return kayit.kopyala() if kayit is not None else None

    def tumunu_listele(
        self,
        durum: Optional[GorevDurumu] = None,
        oncelik: Optional[GorevOnceligi] = None,
        arama_metni: Optional[str] = None,
    ) -> list[Gorev]:
        """Ölçütlere uyan görevleri oluşturulma tarihine göre azalan sırada listeler."""
        with self._kilit:
            sonuclar = list(self._gorevler.values())

        if durum is not None:
            sonuclar = [g for g in sonuclar if g.durum == durum]

        if oncelik is not None:
            sonuclar = [g for g in sonuclar if g.oncelik == oncelik]

        if arama_metni is not None and arama_metni.strip():
            aranan = arama_metni.strip().casefold()
            sonuclar = [
                g
                for g in sonuclar
                if aranan in g.baslik.casefold() or aranan in g.aciklama.casefold()
            ]

        sonuclar.sort(key=lambda g: g.olusturulma_tarihi, reverse=True)
        return [g.kopyala() for g in sonuclar]

    def guncelle(self, gorev: Gorev) -> Gorev:
        """Mevcut görevin güncel durumunu bellek içi depoya yazar."""
        with self._kilit:
            if gorev.id not in self._gorevler:
                raise GorevBulunamadiHatasi(gorev.id)
            self._gorevler[gorev.id] = gorev.kopyala()
            return self._gorevler[gorev.id].kopyala()

    def sil(self, gorev_id: str) -> bool:
        """Kimliğe göre görevi bellek içi depodan siler."""
        with self._kilit:
            if gorev_id not in self._gorevler:
                return False
            del self._gorevler[gorev_id]
            return True

    def temizle(self) -> None:
        """Depodaki tüm kayıtları temizler (özellikle test izolasyonu için)."""
        with self._kilit:
            self._gorevler.clear()
