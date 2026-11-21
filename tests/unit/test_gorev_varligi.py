"""Gorev Zengin Domain Varlığı ve tüm iş kuralları için birim testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.entities.gorev import Gorev
from domain.exceptions.domain_hatalari import (
    GecersizBaslikHatasi,
    GecmisTarihHatasi,
    KilitliGorevHatasi,
    KritikGorevSilinemezHatasi,
)
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


class TestGorevVarligi:
    """Zengin Domain Modeli (Rich Domain Model) davranış testleri."""

    def test_yeni_gorev_varsayilan_beklemede_durumunda_olusturulur(self) -> None:
        ref = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        bitis = ref + timedelta(days=2)

        gorev = Gorev.olustur(
            baslik="  Clean Architecture Uygulaması  ",
            aciklama="  Domain katmanını izole et  ",
            oncelik=GorevOnceligi.YUKSEK,
            bitis_tarihi=bitis,
            referans_zaman=ref,
        )

        assert gorev.id
        assert gorev.baslik == "Clean Architecture Uygulaması"
        assert gorev.aciklama == "Domain katmanını izole et"
        assert gorev.durum == GorevDurumu.BEKLEMEDE
        assert gorev.oncelik == GorevOnceligi.YUKSEK
        assert gorev.bitis_tarihi == bitis
        assert gorev.olusturulma_tarihi == ref
        assert gorev.guncellenme_tarihi == ref

    def test_gecmis_bitis_tarihi_ile_gorev_olusturulamaz(self) -> None:
        ref = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        with pytest.raises(GecmisTarihHatasi):
            Gorev.olustur(
                baslik="Geçmiş Tarihli Görev",
                bitis_tarihi=ref - timedelta(minutes=1),
                referans_zaman=ref,
            )

    def test_guncellemede_gecmis_tarih_reddedilir_ve_alanlar_korunur(self) -> None:
        ref = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        gorev = Gorev.olustur(
            baslik="İlk Başlık",
            aciklama="İlk Açıklama",
            referans_zaman=ref,
        )

        with pytest.raises(GecmisTarihHatasi):
            gorev.guncelle(
                baslik="Değişmemesi Gereken Başlık",
                bitis_tarihi=ref - timedelta(days=1),
                referans_zaman=ref,
            )

        assert gorev.baslik == "İlk Başlık"
        assert gorev.bitis_tarihi is None

    def test_guncellemede_gecersiz_baslik_reddedilir(self) -> None:
        gorev = Gorev.olustur(baslik="Geçerli Başlık")
        with pytest.raises(GecersizBaslikHatasi):
            gorev.guncelle(baslik="ab")
        assert gorev.baslik == "Geçerli Başlık"

    def test_tamamlanmis_gorev_kilitlidir_guncellenemez(self) -> None:
        ref = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
        gorev = Gorev.olustur(
            baslik="Tamamlanacak Görev",
            aciklama="Detay",
            oncelik=GorevOnceligi.ORTA,
            referans_zaman=ref,
        )
        gorev.durum_degistir(GorevDurumu.DEVAM_EDIYOR, referans_zaman=ref)
        gorev.durum_degistir(GorevDurumu.TAMAMLANDI, referans_zaman=ref)

        with pytest.raises(KilitliGorevHatasi) as hata_bilgisi:
            gorev.guncelle(baslik="Yeni Başlık", referans_zaman=ref)
        assert hata_bilgisi.value.hata_kodu == "KILITLI_GOREV"

        with pytest.raises(KilitliGorevHatasi):
            gorev.guncelle(aciklama="Yeni Açıklama", referans_zaman=ref)

        with pytest.raises(KilitliGorevHatasi):
            gorev.guncelle(oncelik=GorevOnceligi.KRITIK, referans_zaman=ref)

        with pytest.raises(KilitliGorevHatasi):
            gorev.guncelle(
                bitis_tarihi=ref + timedelta(days=5), referans_zaman=ref
            )

    def test_kritik_ve_devam_eden_gorev_silinemez(self) -> None:
        gorev = Gorev.olustur(
            baslik="Kritik Operasyon",
            oncelik=GorevOnceligi.KRITIK,
        )
        # BEKLEMEDE iken silinebilir
        gorev.silinebilir_mi_dogrula()

        # DEVAM_EDIYOR iken silinemez
        gorev.durum_degistir(GorevDurumu.DEVAM_EDIYOR)
        with pytest.raises(KritikGorevSilinemezHatasi) as hata_bilgisi:
            gorev.silinebilir_mi_dogrula()
        assert hata_bilgisi.value.hata_kodu == "KRITIK_GOREV_SILINEMEZ"

        # IPTAL_EDILDI durumuna geçince tekrar silinebilir
        gorev.durum_degistir(GorevDurumu.IPTAL_EDILDI)
        gorev.silinebilir_mi_dogrula()

    def test_yuksek_oncelikli_devam_eden_ve_kritik_tamamlanan_silinebilir(
        self,
    ) -> None:
        yuksek_gorev = Gorev.olustur(
            baslik="Yüksek Öncelikli Görev",
            oncelik=GorevOnceligi.YUKSEK,
        )
        yuksek_gorev.durum_degistir(GorevDurumu.DEVAM_EDIYOR)
        yuksek_gorev.silinebilir_mi_dogrula()

        kritik_tamam = Gorev.olustur(
            baslik="Kritik Tamamlanan Görev",
            oncelik=GorevOnceligi.KRITIK,
        )
        kritik_tamam.durum_degistir(GorevDurumu.DEVAM_EDIYOR)
        kritik_tamam.durum_degistir(GorevDurumu.TAMAMLANDI)
        kritik_tamam.silinebilir_mi_dogrula()

    def test_kopyala_bagimsiz_varlik_uretir(self) -> None:
        ozgun = Gorev.olustur(baslik="Özgün Görev")
        kopya = ozgun.kopyala()
        kopya.guncelle(baslik="Kopya Güncellendi")

        assert ozgun == kopya  # Aynı kimlik
        assert ozgun.baslik == "Özgün Görev"
        assert kopya.baslik == "Kopya Güncellendi"
