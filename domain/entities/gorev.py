"""Görev zengin domain varlığı (Rich Domain Model) ve iş kuralları."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from domain.exceptions.domain_hatalari import (
    GecersizDurumGecisiHatasi,
    KilitliGorevHatasi,
    KritikGorevSilinemezHatasi,
)
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi
from domain.value_objects.tarih_dogrulama import (
    BitisTarihi,
    GorevBasligi,
    tarihi_utc_normalize_et,
    utc_simdi,
)


class Gorev:
    """Kendi iş kurallarını ve durum değişmezlerini koruyan Zengin Domain Varlığı."""

    def __init__(
        self,
        gorev_id: str,
        baslik: GorevBasligi,
        aciklama: str,
        durum: GorevDurumu,
        oncelik: GorevOnceligi,
        bitis_tarihi: Optional[BitisTarihi],
        olusturulma_tarihi: datetime,
        guncellenme_tarihi: datetime,
    ) -> None:
        self._id: str = gorev_id
        self._baslik: GorevBasligi = baslik
        self._aciklama: str = aciklama
        self._durum: GorevDurumu = durum
        self._oncelik: GorevOnceligi = oncelik
        self._bitis_tarihi: Optional[BitisTarihi] = bitis_tarihi
        self._olusturulma_tarihi: datetime = olusturulma_tarihi
        self._guncellenme_tarihi: datetime = guncellenme_tarihi

    @classmethod
    def olustur(
        cls,
        baslik: str,
        aciklama: str = "",
        oncelik: GorevOnceligi = GorevOnceligi.ORTA,
        bitis_tarihi: Optional[datetime] = None,
        gorev_id: Optional[str] = None,
        referans_zaman: Optional[datetime] = None,
    ) -> Gorev:
        """İş kurallarını doğrulayarak yeni bir görev varlığı oluşturur."""
        simdi = (
            tarihi_utc_normalize_et(referans_zaman)
            if referans_zaman is not None
            else utc_simdi()
        )
        gecerli_baslik = GorevBasligi(baslik)
        gecerli_bitis = (
            BitisTarihi.olustur(bitis_tarihi, referans_zaman=simdi)
            if bitis_tarihi is not None
            else None
        )
        temiz_aciklama = aciklama.strip() if isinstance(aciklama, str) else ""
        atanan_id = gorev_id if gorev_id else str(uuid4())

        return cls(
            gorev_id=atanan_id,
            baslik=gecerli_baslik,
            aciklama=temiz_aciklama,
            durum=GorevDurumu.BEKLEMEDE,
            oncelik=oncelik,
            bitis_tarihi=gecerli_bitis,
            olusturulma_tarihi=simdi,
            guncellenme_tarihi=simdi,
        )

    @classmethod
    def yeniden_olustur(
        cls,
        gorev_id: str,
        baslik: str,
        aciklama: str,
        durum: GorevDurumu,
        oncelik: GorevOnceligi,
        bitis_tarihi: Optional[datetime],
        olusturulma_tarihi: datetime,
        guncellenme_tarihi: datetime,
    ) -> Gorev:
        """Kalıcı depodan okunan verilerden görev varlığını yeniden yapılandırır."""
        gecerli_bitis = (
            BitisTarihi.mevcut_kayittan_yukle(bitis_tarihi)
            if bitis_tarihi is not None
            else None
        )
        return cls(
            gorev_id=gorev_id,
            baslik=GorevBasligi(baslik),
            aciklama=aciklama,
            durum=durum,
            oncelik=oncelik,
            bitis_tarihi=gecerli_bitis,
            olusturulma_tarihi=tarihi_utc_normalize_et(olusturulma_tarihi),
            guncellenme_tarihi=tarihi_utc_normalize_et(guncellenme_tarihi),
        )

    @property
    def id(self) -> str:
        """Görevin benzersiz kimliği."""
        return self._id

    @property
    def baslik(self) -> str:
        """Görevin doğrulanmış başlık metni."""
        return self._baslik.deger

    @property
    def aciklama(self) -> str:
        """Görevin detaylı açıklaması."""
        return self._aciklama

    @property
    def durum(self) -> GorevDurumu:
        """Görevin mevcut yaşam döngüsü durumu."""
        return self._durum

    @property
    def oncelik(self) -> GorevOnceligi:
        """Görevin öncelik seviyesi."""
        return self._oncelik

    @property
    def bitis_tarihi(self) -> Optional[datetime]:
        """Görevin UTC normalize edilmiş son teslim tarihi."""
        return self._bitis_tarihi.deger if self._bitis_tarihi is not None else None

    @property
    def olusturulma_tarihi(self) -> datetime:
        """Görevin oluşturulma zaman damgası (UTC)."""
        return self._olusturulma_tarihi

    @property
    def guncellenme_tarihi(self) -> datetime:
        """Görevin son güncellenme zaman damgası (UTC)."""
        return self._guncellenme_tarihi

    def guncelle(
        self,
        baslik: Optional[str] = None,
        aciklama: Optional[str] = None,
        oncelik: Optional[GorevOnceligi] = None,
        bitis_tarihi: Optional[datetime] = None,
        bitis_tarihini_temizle: bool = False,
        referans_zaman: Optional[datetime] = None,
    ) -> None:
        """Görev alanlarını iş kurallarını koruyarak günceller."""
        if self._durum == GorevDurumu.TAMAMLANDI:
            raise KilitliGorevHatasi(
                "Tamamlanmış (TAMAMLANDI) durumundaki bir görev salt okunurdur; "
                "başlığı, açıklaması, önceliği veya bitiş tarihi değiştirilemez."
            )

        simdi = (
            tarihi_utc_normalize_et(referans_zaman)
            if referans_zaman is not None
            else utc_simdi()
        )

        yeni_baslik = GorevBasligi(baslik) if baslik is not None else self._baslik
        yeni_bitis = self._bitis_tarihi
        if bitis_tarihi is not None:
            yeni_bitis = BitisTarihi.olustur(bitis_tarihi, referans_zaman=simdi)
        elif bitis_tarihini_temizle:
            yeni_bitis = None

        self._baslik = yeni_baslik
        if aciklama is not None:
            self._aciklama = aciklama.strip()
        if oncelik is not None:
            self._oncelik = oncelik
        self._bitis_tarihi = yeni_bitis
        self._guncellenme_tarihi = simdi

    def durum_degistir(
        self,
        yeni_durum: GorevDurumu,
        referans_zaman: Optional[datetime] = None,
    ) -> None:
        """Durum makinesi kurallarına göre görev durumunu değiştirir."""
        if self._durum == GorevDurumu.IPTAL_EDILDI:
            raise GecersizDurumGecisiHatasi(
                "İptal edilmiş (IPTAL_EDILDI) durumundaki bir görev yeniden "
                "başlatılamaz veya başka bir duruma geçirilemez."
            )

        if self._durum == GorevDurumu.TAMAMLANDI:
            raise GecersizDurumGecisiHatasi(
                "Tamamlanmış (TAMAMLANDI) durumundaki bir görevin durumu değiştirilemez."
            )

        if (
            self._durum == GorevDurumu.BEKLEMEDE
            and yeni_durum == GorevDurumu.TAMAMLANDI
        ):
            raise GecersizDurumGecisiHatasi(
                "BEKLEMEDE durumundaki bir görev doğrudan TAMAMLANDI durumuna "
                "geçirilemez; önce DEVAM_EDIYOR aşamasından geçmelidir."
            )

        if self._durum == yeni_durum:
            raise GecersizDurumGecisiHatasi(
                f"Görev zaten '{self._durum.value}' durumundadır."
            )

        if not self._durum.gecis_yapilabilir_mi(yeni_durum):
            raise GecersizDurumGecisiHatasi(
                f"'{self._durum.value}' durumundan '{yeni_durum.value}' "
                "durumuna geçiş yapılamaz."
            )

        simdi = (
            tarihi_utc_normalize_et(referans_zaman)
            if referans_zaman is not None
            else utc_simdi()
        )
        self._durum = yeni_durum
        self._guncellenme_tarihi = simdi

    def silinebilir_mi_dogrula(self) -> None:
        """Görevin silinip silinemeyeceğini iş kurallarına göre doğrular."""
        if (
            self._oncelik == GorevOnceligi.KRITIK
            and self._durum == GorevDurumu.DEVAM_EDIYOR
        ):
            raise KritikGorevSilinemezHatasi(
                "Önceliği KRITIK ve durumu DEVAM_EDIYOR olan bir görev doğrudan "
                "silinemez; önce IPTAL_EDILDI durumuna alınmalıdır."
            )

    def izinli_durum_gecisleri(self) -> list[GorevDurumu]:
        """Mevcut durumdan geçilebilecek geçerli hedef durumların listesini döndürür."""
        return [
            durum for durum in GorevDurumu if self._durum.gecis_yapilabilir_mi(durum)
        ]

    def kopyala(self) -> Gorev:
        """Varlığın dış mutasyonlardan yalıtılmış bağımsız bir kopyasını oluşturur."""
        return Gorev.yeniden_olustur(
            gorev_id=self._id,
            baslik=self.baslik,
            aciklama=self._aciklama,
            durum=self._durum,
            oncelik=self._oncelik,
            bitis_tarihi=self.bitis_tarihi,
            olusturulma_tarihi=self._olusturulma_tarihi,
            guncellenme_tarihi=self._guncellenme_tarihi,
        )

    def __eq__(self, diger: object) -> bool:
        if not isinstance(diger, Gorev):
            return NotImplemented
        return self._id == diger._id

    def __repr__(self) -> str:
        return (
            f"Gorev(id={self._id!r}, baslik={self.baslik!r}, "
            f"durum={self._durum.value!r}, oncelik={self._oncelik.value!r})"
        )
