"""Use Case katmanı için In-Memory ve SQLite parametreli entegrasyon testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from application.dtos.gorev_dto import (
    GorevDurumDegistirGirdi,
    GorevFiltreGirdi,
    GorevGuncelleGirdi,
    GorevOlusturGirdi,
)
from application.use_cases.gorev_durum_degistir import GorevDurumDegistirUseCase
from application.use_cases.gorev_getir import GorevGetirUseCase
from application.use_cases.gorev_guncelle import GorevGuncelleUseCase
from application.use_cases.gorev_listele import GorevListeleUseCase
from application.use_cases.gorev_olustur import GorevOlusturUseCase
from application.use_cases.gorev_sil import GorevSilUseCase
from domain.exceptions.domain_hatalari import (
    GorevBulunamadiHatasi,
    KilitliGorevHatasi,
    KritikGorevSilinemezHatasi,
)
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


class TestUseCaseEntegrasyon:
    """Tüm Use Case sınıflarının her iki repository adaptörüyle aynı çalıştığını doğrular."""

    def test_gorev_olustur_getir_ve_listele_filtreleme(
        self, repository: GorevRepositoryArayuzu
    ) -> None:
        olustur_uc = GorevOlusturUseCase(repository)
        getir_uc = GorevGetirUseCase(repository)
        listele_uc = GorevListeleUseCase(repository)
        durum_uc = GorevDurumDegistirUseCase(repository)

        gelecek = datetime.now(timezone.utc) + timedelta(days=5)
        g1 = olustur_uc.calistir(
            GorevOlusturGirdi(
                baslik="Mimari İstatistik Raporu",
                aciklama="Clean Architecture metriklerini derle",
                oncelik=GorevOnceligi.YUKSEK,
                bitis_tarihi=gelecek,
            )
        )
        g2 = olustur_uc.calistir(
            GorevOlusturGirdi(
                baslik="Birim Testlerini Genişlet",
                aciklama="Boundary durumlarını ekle",
                oncelik=GorevOnceligi.DUSUK,
            )
        )

        durum_uc.calistir(
            GorevDurumDegistirGirdi(
                gorev_id=g1.id, yeni_durum=GorevDurumu.DEVAM_EDIYOR
            )
        )

        tekil = getir_uc.calistir(g1.id)
        assert tekil.id == g1.id
        assert tekil.durum == GorevDurumu.DEVAM_EDIYOR
        assert set(tekil.izinli_gecisler) == {
            GorevDurumu.BEKLEMEDE,
            GorevDurumu.TAMAMLANDI,
            GorevDurumu.IPTAL_EDILDI,
        }

        tum_liste = listele_uc.calistir()
        assert len(tum_liste) == 2

        devam_edenler = listele_uc.calistir(
            GorevFiltreGirdi(durum=GorevDurumu.DEVAM_EDIYOR)
        )
        assert [g.id for g in devam_edenler] == [g1.id]

        dusuk_oncelikliler = listele_uc.calistir(
            GorevFiltreGirdi(oncelik=GorevOnceligi.DUSUK)
        )
        assert [g.id for g in dusuk_oncelikliler] == [g2.id]

        aranan = listele_uc.calistir(GorevFiltreGirdi(arama_metni="clean architecture"))
        assert [g.id for g in aranan] == [g1.id]

    def test_guncelle_durum_degistir_ve_kilit_kurali(
        self, repository: GorevRepositoryArayuzu
    ) -> None:
        olustur_uc = GorevOlusturUseCase(repository)
        guncelle_uc = GorevGuncelleUseCase(repository)
        durum_uc = GorevDurumDegistirUseCase(repository)

        gelecek = datetime.now(timezone.utc) + timedelta(days=3)
        gorev = olustur_uc.calistir(
            GorevOlusturGirdi(
                baslik="İlk Görev",
                aciklama="İlk açıklama",
                oncelik=GorevOnceligi.ORTA,
                bitis_tarihi=gelecek,
            )
        )

        guncellenen = guncelle_uc.calistir(
            GorevGuncelleGirdi(
                gorev_id=gorev.id,
                baslik="Güncellenmiş Görev",
                oncelik=GorevOnceligi.YUKSEK,
                bitis_tarihini_temizle=True,
            )
        )
        assert guncellenen.baslik == "Güncellenmiş Görev"
        assert guncellenen.oncelik == GorevOnceligi.YUKSEK
        assert guncellenen.bitis_tarihi is None

        durum_uc.calistir(
            GorevDurumDegistirGirdi(
                gorev_id=gorev.id, yeni_durum=GorevDurumu.DEVAM_EDIYOR
            )
        )
        tamamlanan = durum_uc.calistir(
            GorevDurumDegistirGirdi(
                gorev_id=gorev.id, yeni_durum=GorevDurumu.TAMAMLANDI
            )
        )
        assert tamamlanan.durum == GorevDurumu.TAMAMLANDI
        assert tamamlanan.izinli_gecisler == ()

        with pytest.raises(KilitliGorevHatasi):
            guncelle_uc.calistir(
                GorevGuncelleGirdi(gorev_id=gorev.id, baslik="Kilitli Değişiklik")
            )

    def test_kritik_gorev_silme_korumasi_ve_silme_akisi(
        self, repository: GorevRepositoryArayuzu
    ) -> None:
        olustur_uc = GorevOlusturUseCase(repository)
        durum_uc = GorevDurumDegistirUseCase(repository)
        sil_uc = GorevSilUseCase(repository)
        getir_uc = GorevGetirUseCase(repository)

        kritik = olustur_uc.calistir(
            GorevOlusturGirdi(
                baslik="Acil Veritabanı Kurtarma",
                oncelik=GorevOnceligi.KRITIK,
            )
        )
        durum_uc.calistir(
            GorevDurumDegistirGirdi(
                gorev_id=kritik.id, yeni_durum=GorevDurumu.DEVAM_EDIYOR
            )
        )

        with pytest.raises(KritikGorevSilinemezHatasi):
            sil_uc.calistir(kritik.id)

        durum_uc.calistir(
            GorevDurumDegistirGirdi(
                gorev_id=kritik.id, yeni_durum=GorevDurumu.IPTAL_EDILDI
            )
        )
        sil_uc.calistir(kritik.id)

        with pytest.raises(GorevBulunamadiHatasi):
            getir_uc.calistir(kritik.id)

    def test_olmayan_gorev_kimligi_hata_firlatir(
        self, repository: GorevRepositoryArayuzu
    ) -> None:
        olmayan_id = "mevcut-olmayan-uuid"
        with pytest.raises(GorevBulunamadiHatasi):
            GorevGetirUseCase(repository).calistir(olmayan_id)
        with pytest.raises(GorevBulunamadiHatasi):
            GorevGuncelleUseCase(repository).calistir(
                GorevGuncelleGirdi(gorev_id=olmayan_id, baslik="Yeni")
            )
        with pytest.raises(GorevBulunamadiHatasi):
            GorevDurumDegistirUseCase(repository).calistir(
                GorevDurumDegistirGirdi(
                    gorev_id=olmayan_id, yeni_durum=GorevDurumu.DEVAM_EDIYOR
                )
            )
        with pytest.raises(GorevBulunamadiHatasi):
            GorevSilUseCase(repository).calistir(olmayan_id)
