"""Görev başlığı ve son teslim tarihi doğrulamalarını kapsayan değer nesneleri."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import ClassVar, Optional

from domain.exceptions.domain_hatalari import (
    GecersizBaslikHatasi,
    GecmisTarihHatasi,
)


def utc_simdi() -> datetime:
    """UTC saat diliminde güncel zaman damgasını döndürür."""
    return datetime.now(timezone.utc)


def tarihi_utc_normalize_et(tarih: datetime) -> datetime:
    """Tarihi UTC farkındalıklı (timezone-aware) hale getirir.

    Saat dilimi bilgisi içermeyen (naive) tarihler UTC kabul edilir;
    farklı bir saat dilimi içerenler UTC'ye dönüştürülür.
    """
    if tarih.tzinfo is None or tarih.tzinfo.utcoffset(tarih) is None:
        return tarih.replace(tzinfo=timezone.utc)
    return tarih.astimezone(timezone.utc)


@dataclass(frozen=True)
class GorevBasligi:
    """En az 3, en fazla 100 karakter uzunluğunda geçerli görev başlığı değer nesnesi."""

    MIN_UZUNLUK: ClassVar[int] = 3
    MAX_UZUNLUK: ClassVar[int] = 100

    deger: str

    def __post_init__(self) -> None:
        if not isinstance(self.deger, str):
            raise GecersizBaslikHatasi("Görev başlığı metin tipinde olmalıdır.")

        temizlenmis = self.deger.strip()
        if not temizlenmis:
            raise GecersizBaslikHatasi("Görev başlığı boş bırakılamaz.")

        uzunluk = len(temizlenmis)
        if uzunluk < self.MIN_UZUNLUK or uzunluk > self.MAX_UZUNLUK:
            raise GecersizBaslikHatasi(
                f"Görev başlığı en az {self.MIN_UZUNLUK}, en fazla "
                f"{self.MAX_UZUNLUK} karakter olmalıdır (girilen: {uzunluk})."
            )

        object.__setattr__(self, "deger", temizlenmis)


@dataclass(frozen=True)
class BitisTarihi:
    """UTC normalize edilmiş ve geçmiş tarih kuralını koruyan son teslim tarihi değer nesnesi."""

    deger: datetime

    @classmethod
    def olustur(
        cls,
        tarih: datetime,
        referans_zaman: Optional[datetime] = None,
    ) -> BitisTarihi:
        """Yeni atanan son teslim tarihinin geçmişte olmadığını doğrulayarak değer nesnesi üretir."""
        if not isinstance(tarih, datetime):
            raise GecmisTarihHatasi("Son teslim tarihi geçerli bir tarih/saat olmalıdır.")

        hedef_utc = tarihi_utc_normalize_et(tarih)
        ref_utc = tarihi_utc_normalize_et(
            referans_zaman if referans_zaman is not None else utc_simdi()
        )

        if hedef_utc < ref_utc:
            raise GecmisTarihHatasi(
                "Son teslim tarihi geçmiş bir tarih olamaz."
            )

        return cls(deger=hedef_utc)

    @classmethod
    def mevcut_kayittan_yukle(cls, tarih: datetime) -> BitisTarihi:
        """Kalıcı depodan okunan mevcut tarih değerini geçmiş kontrolü yapmadan yükler."""
        return cls(deger=tarihi_utc_normalize_et(tarih))
