"""Application katmanı DTO tanımları (çerçeveden bağımsız saf Python dataclass)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.entities.gorev import Gorev
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


@dataclass(frozen=True)
class GorevOlusturGirdi:
    """Yeni görev oluşturma kullanım senaryosu için girdi DTO'su."""

    baslik: str
    aciklama: str = ""
    oncelik: GorevOnceligi = GorevOnceligi.ORTA
    bitis_tarihi: Optional[datetime] = None


@dataclass(frozen=True)
class GorevGuncelleGirdi:
    """Mevcut görevi güncelleme kullanım senaryosu için girdi DTO'su."""

    gorev_id: str
    baslik: Optional[str] = None
    aciklama: Optional[str] = None
    oncelik: Optional[GorevOnceligi] = None
    bitis_tarihi: Optional[datetime] = None
    bitis_tarihini_temizle: bool = False


@dataclass(frozen=True)
class GorevDurumDegistirGirdi:
    """Görev durumu değiştirme kullanım senaryosu için girdi DTO'su."""

    gorev_id: str
    yeni_durum: GorevDurumu


@dataclass(frozen=True)
class GorevFiltreGirdi:
    """Görev listeleme ve arama ölçütleri için girdi DTO'su."""

    durum: Optional[GorevDurumu] = None
    oncelik: Optional[GorevOnceligi] = None
    arama_metni: Optional[str] = None


@dataclass(frozen=True)
class GorevCikti:
    """Dış katmanlara döndürülen görev çıktı DTO'su."""

    id: str
    baslik: str
    aciklama: str
    durum: GorevDurumu
    oncelik: GorevOnceligi
    bitis_tarihi: Optional[datetime]
    olusturulma_tarihi: datetime
    guncellenme_tarihi: datetime
    izinli_gecisler: tuple[GorevDurumu, ...]

    @classmethod
    def varliktan_olustur(cls, gorev: Gorev) -> GorevCikti:
        """Domain Gorev varlığını uygulama katmanı çıktı DTO'suna dönüştürür."""
        return cls(
            id=gorev.id,
            baslik=gorev.baslik,
            aciklama=gorev.aciklama,
            durum=gorev.durum,
            oncelik=gorev.oncelik,
            bitis_tarihi=gorev.bitis_tarihi,
            olusturulma_tarihi=gorev.olusturulma_tarihi,
            guncellenme_tarihi=gorev.guncellenme_tarihi,
            izinli_gecisler=tuple(gorev.izinli_durum_gecisleri()),
        )
