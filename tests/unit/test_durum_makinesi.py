"""Görev durum makinesi (State Machine) için kapsamlı birim testleri."""

from __future__ import annotations

import pytest

from domain.entities.gorev import Gorev
from domain.exceptions.domain_hatalari import GecersizDurumGecisiHatasi
from domain.value_objects.gorev_durumu import GorevDurumu


def _gorevi_duruma_getir(hedef: GorevDurumu) -> Gorev:
    gorev = Gorev.olustur(baslik="Durum Makinesi Test Görevi")
    if hedef == GorevDurumu.BEKLEMEDE:
        return gorev
    if hedef == GorevDurumu.DEVAM_EDIYOR:
        gorev.durum_degistir(GorevDurumu.DEVAM_EDIYOR)
        return gorev
    if hedef == GorevDurumu.TAMAMLANDI:
        gorev.durum_degistir(GorevDurumu.DEVAM_EDIYOR)
        gorev.durum_degistir(GorevDurumu.TAMAMLANDI)
        return gorev
    gorev.durum_degistir(GorevDurumu.IPTAL_EDILDI)
    return gorev


IZINLI_MATRIS: set[tuple[GorevDurumu, GorevDurumu]] = {
    (GorevDurumu.BEKLEMEDE, GorevDurumu.DEVAM_EDIYOR),
    (GorevDurumu.BEKLEMEDE, GorevDurumu.IPTAL_EDILDI),
    (GorevDurumu.DEVAM_EDIYOR, GorevDurumu.TAMAMLANDI),
    (GorevDurumu.DEVAM_EDIYOR, GorevDurumu.BEKLEMEDE),
    (GorevDurumu.DEVAM_EDIYOR, GorevDurumu.IPTAL_EDILDI),
}


class TestDurumMakinesi:
    """Durum geçiş matrisi (Kural 2) testleri."""

    @pytest.mark.parametrize("kaynak", list(GorevDurumu))
    @pytest.mark.parametrize("hedef", list(GorevDurumu))
    def test_tum_durum_gecis_matrisi(
        self, kaynak: GorevDurumu, hedef: GorevDurumu
    ) -> None:
        gorev = _gorevi_duruma_getir(kaynak)
        gecis_izinli = (kaynak, hedef) in IZINLI_MATRIS

        assert kaynak.gecis_yapilabilir_mi(hedef) is gecis_izinli

        if gecis_izinli:
            gorev.durum_degistir(hedef)
            assert gorev.durum == hedef
        else:
            with pytest.raises(GecersizDurumGecisiHatasi) as hata_bilgisi:
                gorev.durum_degistir(hedef)
            assert hata_bilgisi.value.hata_kodu == "GECERSIZ_DURUM_GECISI"
            assert gorev.durum == kaynak

    def test_beklemeden_dogrudan_tamamlandiya_gecis_yasakli(self) -> None:
        gorev = Gorev.olustur(baslik="Doğrudan Tamamlanamaz Görev")
        with pytest.raises(GecersizDurumGecisiHatasi) as hata_bilgisi:
            gorev.durum_degistir(GorevDurumu.TAMAMLANDI)
        assert "DEVAM_EDIYOR" in hata_bilgisi.value.mesaj

    @pytest.mark.parametrize(
        "hedef",
        [GorevDurumu.BEKLEMEDE, GorevDurumu.DEVAM_EDIYOR, GorevDurumu.TAMAMLANDI],
    )
    def test_iptal_edilmis_gorev_yeniden_baslatilamaz(
        self, hedef: GorevDurumu
    ) -> None:
        gorev = _gorevi_duruma_getir(GorevDurumu.IPTAL_EDILDI)
        with pytest.raises(GecersizDurumGecisiHatasi):
            gorev.durum_degistir(hedef)
        assert gorev.izinli_durum_gecisleri() == []
