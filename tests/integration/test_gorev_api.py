"""FastAPI REST API ve Global Exception Handler uçtan uca entegrasyon testleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri


class TestGorevApi:
    """Hem In-Memory hem de SQLite üzerinde özdeş API davranışını test eder."""

    def test_web_paneli_swagger_ve_sistem_bilgisi(
        self, api_istemcisi: tuple[TestClient, str]
    ) -> None:
        istemci, beklenen_repo = api_istemcisi

        ui_yaniti = istemci.get("/")
        assert ui_yaniti.status_code == 200
        assert "text/html" in ui_yaniti.headers["content-type"]
        assert "Görev Yönetim Sistemi" in ui_yaniti.text

        docs_yaniti = istemci.get("/docs")
        assert docs_yaniti.status_code == 200

        sistem_yaniti = istemci.get("/api/v1/sistem")
        assert sistem_yaniti.status_code == 200
        veri = sistem_yaniti.json()
        assert veri["aktif_repository"] == beklenen_repo
        assert veri["durum"] == "calisiyor"

    def test_tam_crud_ve_filtreleme_yasam_dongusu(
        self, api_istemcisi: tuple[TestClient, str]
    ) -> None:
        istemci, _ = api_istemcisi
        gelecek = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        olusturma = istemci.post(
            "/api/v1/gorevler",
            json={
                "baslik": "REST API Uç Noktalarını Doğrula",
                "aciklama": "Swagger şeması ve CRUD akışını test et",
                "oncelik": "YUKSEK",
                "bitis_tarihi": gelecek,
            },
        )
        assert olusturma.status_code == 201
        gorev = olusturma.json()
        gorev_id = gorev["id"]
        assert gorev["durum"] == "BEKLEMEDE"
        assert gorev["oncelik"] == "YUKSEK"
        assert set(gorev["izinli_gecisler"]) == {"DEVAM_EDIYOR", "IPTAL_EDILDI"}

        # Tekil getirme
        tekil = istemci.get(f"/api/v1/gorevler/{gorev_id}")
        assert tekil.status_code == 200
        assert tekil.json()["baslik"] == "REST API Uç Noktalarını Doğrula"

        # Listeleme ve filtreleme
        liste = istemci.get(
            "/api/v1/gorevler",
            params={"durum": "BEKLEMEDE", "oncelik": "YUKSEK", "arama": "Swagger"},
        )
        assert liste.status_code == 200
        assert len(liste.json()) == 1
        assert liste.json()[0]["id"] == gorev_id

        # Güncelleme
        guncelleme = istemci.put(
            f"/api/v1/gorevler/{gorev_id}",
            json={
                "baslik": "Güncel API Görevi",
                "aciklama": "Açıklama yenilendi",
                "oncelik": "ORTA",
            },
        )
        assert guncelleme.status_code == 200
        assert guncelleme.json()["baslik"] == "Güncel API Görevi"
        assert guncelleme.json()["oncelik"] == "ORTA"

        # Durum geçişi
        durum_yanit = istemci.patch(
            f"/api/v1/gorevler/{gorev_id}/durum",
            json={"yeni_durum": "DEVAM_EDIYOR"},
        )
        assert durum_yanit.status_code == 200
        assert durum_yanit.json()["durum"] == "DEVAM_EDIYOR"

        # Silme
        silme = istemci.delete(f"/api/v1/gorevler/{gorev_id}")
        assert silme.status_code == 204

        # Silindikten sonra 404
        sonraki_getir = istemci.get(f"/api/v1/gorevler/{gorev_id}")
        assert sonraki_getir.status_code == 404
        assert sonraki_getir.json()["hata_kodu"] == "GOREV_BULUNAMADI"

    def test_is_kurallari_http_hata_eslemeleri(
        self, api_istemcisi: tuple[TestClient, str]
    ) -> None:
        istemci, _ = api_istemcisi
        gecmis = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()

        # Kural 5: Kısa / boş / uzun başlık -> 422 GECERSIZ_BASLIK
        for hatali_baslik in ["", "  ", "ab", "a" * 101]:
            yanit = istemci.post(
                "/api/v1/gorevler",
                json={"baslik": hatali_baslik},
            )
            assert yanit.status_code == 422
            assert yanit.json()["hata_kodu"] == "GECERSIZ_BASLIK"

        # Kural 1: Geçmiş tarihle oluşturma -> 422 GECMIS_TARIH
        gecmis_yanit = istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "Geçmiş Tarihli İstek", "bitis_tarihi": gecmis},
        )
        assert gecmis_yanit.status_code == 422
        assert gecmis_yanit.json()["hata_kodu"] == "GECMIS_TARIH"

        # Geçerli görev oluştur
        olustur = istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "Kuralları Doğrulama Görevi", "oncelik": "KRITIK"},
        )
        assert olustur.status_code == 201
        gorev_id = olustur.json()["id"]

        # Kural 1 (güncelleme): Geçmiş tarihle güncelleme -> 422 GECMIS_TARIH
        gecmis_guncelle = istemci.put(
            f"/api/v1/gorevler/{gorev_id}",
            json={"bitis_tarihi": gecmis},
        )
        assert gecmis_guncelle.status_code == 422
        assert gecmis_guncelle.json()["hata_kodu"] == "GECMIS_TARIH"

        # Kural 2: BEKLEMEDE -> TAMAMLANDI doğrudan geçişi -> 400 GECERSIZ_DURUM_GECISI
        dogrudan_tamamla = istemci.patch(
            f"/api/v1/gorevler/{gorev_id}/durum",
            json={"yeni_durum": "TAMAMLANDI"},
        )
        assert dogrudan_tamamla.status_code == 400
        assert dogrudan_tamamla.json()["hata_kodu"] == "GECERSIZ_DURUM_GECISI"

        # DEVAM_EDIYOR durumuna çek
        baslat = istemci.patch(
            f"/api/v1/gorevler/{gorev_id}/durum",
            json={"yeni_durum": "DEVAM_EDIYOR"},
        )
        assert baslat.status_code == 200

        # Kural 4: KRITIK + DEVAM_EDIYOR doğrudan silinemez -> 400 KRITIK_GOREV_SILINEMEZ
        kritik_sil = istemci.delete(f"/api/v1/gorevler/{gorev_id}")
        assert kritik_sil.status_code == 400
        assert kritik_sil.json()["hata_kodu"] == "KRITIK_GOREV_SILINEMEZ"

        # Tamamla ve Kural 3'ü doğrula: TAMAMLANDI görev kilitlidir -> 400 KILITLI_GOREV
        tamamla = istemci.patch(
            f"/api/v1/gorevler/{gorev_id}/durum",
            json={"yeni_durum": "TAMAMLANDI"},
        )
        assert tamamla.status_code == 200

        kilitli_guncelle = istemci.put(
            f"/api/v1/gorevler/{gorev_id}",
            json={"baslik": "Kilitli Görev Değişimi"},
        )
        assert kilitli_guncelle.status_code == 400
        assert kilitli_guncelle.json()["hata_kodu"] == "KILITLI_GOREV"

        # Kural 2 (iptal sonrası yeniden başlatılamaz)
        iptal_gorev = istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "İptal Edilecek Görev"},
        ).json()
        iptal_id = iptal_gorev["id"]

        assert (
            istemci.patch(
                f"/api/v1/gorevler/{iptal_id}/durum",
                json={"yeni_durum": "IPTAL_EDILDI"},
            ).status_code
            == 200
        )
        yeniden_baslat = istemci.patch(
            f"/api/v1/gorevler/{iptal_id}/durum",
            json={"yeni_durum": "DEVAM_EDIYOR"},
        )
        assert yeniden_baslat.status_code == 400
        assert yeniden_baslat.json()["hata_kodu"] == "GECERSIZ_DURUM_GECISI"


class TestOrtamDegiskeniIleRepoSecimi:
    """REPO_TYPE ortam değişkeni ile dinamik repository seçimini doğrular."""

    def test_ortam_degiskeniyle_memory_ve_sqlite_secimi(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.setenv("REPO_TYPE", "memory")
        ayarlar_mem = Ayarlar.ortamdan_yukle()
        konteyner_mem = BagimlilikKonteyneri(ayarlar=ayarlar_mem)
        assert konteyner_mem.aktif_repo_tipi == "memory"
        konteyner_mem.kapat()

        db_yolu = tmp_path / "env_test.db"
        monkeypatch.setenv("REPO_TYPE", "sqlite")
        monkeypatch.setenv("SQLITE_DB_PATH", str(db_yolu))
        ayarlar_sql = Ayarlar.ortamdan_yukle()
        konteyner_sql = BagimlilikKonteyneri(ayarlar=ayarlar_sql)
        assert konteyner_sql.aktif_repo_tipi == "sqlite"
        konteyner_sql.kapat()
        assert db_yolu.exists()

    def test_gecersiz_repo_tipi_hata_vermeli(self) -> None:
        with pytest.raises(ValueError, match="Geçersiz REPO_TYPE"):
            Ayarlar(repo_tipi="redis")
