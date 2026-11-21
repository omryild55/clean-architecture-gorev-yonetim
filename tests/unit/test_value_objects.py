"""Domain değer nesneleri (Value Objects) için birim testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.exceptions.domain_hatalari import (
    GecersizBaslikHatasi,
    GecmisTarihHatasi,
)
from domain.value_objects.tarih_dogrulama import (
    BitisTarihi,
    GorevBasligi,
    tarihi_utc_normalize_et,
)


class TestGorevBasligi:
    """Başlık doğrulama kuralları (Kural 5) testleri."""

    @pytest.mark.parametrize(
        "gecersiz_baslik",
        [
            "",
            "   ",
            "\t\n",
            "ab",
            " a ",
            "x" * 101,
        ],
    )
    def test_gecersiz_basliklar_reddedilmeli(self, gecersiz_baslik: str) -> None:
        with pytest.raises(GecersizBaslikHatasi) as hata_bilgisi:
            GorevBasligi(gecersiz_baslik)
        assert hata_bilgisi.value.hata_kodu == "GECERSIZ_BASLIK"

    def test_metin_olmayan_baslik_reddedilmeli(self) -> None:
        with pytest.raises(GecersizBaslikHatasi):
            GorevBasligi(None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("ham_baslik", "beklenen"),
        [
            ("abc", "abc"),
            ("  Test Görevi  ", "Test Görevi"),
            ("x" * 100, "x" * 100),
            ("   " + ("a" * 100) + "   ", "a" * 100),
        ],
    )
    def test_gecerli_sinir_basliklar_kabul_edilmeli_ve_kirpilmali(
        self, ham_baslik: str, beklenen: str
    ) -> None:
        baslik = GorevBasligi(ham_baslik)
        assert baslik.deger == beklenen


class TestBitisTarihi:
    """Son teslim tarihi ve UTC normalizasyon kuralları (Kural 1) testleri."""

    def test_gecmis_tarih_reddedilmeli(self) -> None:
        referans = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        gecmis = referans - timedelta(seconds=1)

        with pytest.raises(GecmisTarihHatasi) as hata_bilgisi:
            BitisTarihi.olustur(gecmis, referans_zaman=referans)
        assert hata_bilgisi.value.hata_kodu == "GECMIS_TARIH"

    def test_referans_ile_ayni_veya_gelecek_tarih_kabul_edilmeli(self) -> None:
        referans = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)

        ayni_an = BitisTarihi.olustur(referans, referans_zaman=referans)
        gelecek = BitisTarihi.olustur(
            referans + timedelta(days=3), referans_zaman=referans
        )

        assert ayni_an.deger == referans
        assert gelecek.deger == referans + timedelta(days=3)

    def test_farkli_saat_dilimi_ve_naive_tarih_utc_normalize_edilmeli(self) -> None:
        referans = datetime(2026, 5, 10, 10, 0, 0, tzinfo=timezone.utc)
        istanbul_tz = timezone(timedelta(hours=3))
        istanbul_saati = datetime(2026, 5, 10, 15, 0, 0, tzinfo=istanbul_tz)

        sonuc = BitisTarihi.olustur(istanbul_saati, referans_zaman=referans)
        assert sonuc.deger.tzinfo == timezone.utc
        assert sonuc.deger == datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)

        naive_tarih = datetime(2026, 5, 10, 12, 0, 0)
        assert tarihi_utc_normalize_et(naive_tarih).tzinfo == timezone.utc

    def test_mevcut_kayittan_gecmis_tarih_yuklenebilmeli(self) -> None:
        eski_tarih = datetime(2020, 1, 1, 8, 30, 0)
        yuklenen = BitisTarihi.mevcut_kayittan_yukle(eski_tarih)
        assert yuklenen.deger == datetime(2020, 1, 1, 8, 30, 0, tzinfo=timezone.utc)
