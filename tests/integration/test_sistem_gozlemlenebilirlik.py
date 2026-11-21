"""Sistem gözlemlenebilirliği, DIP adaptör değişimi, AST denetimi ve log entegrasyon testleri."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri
from main import uygulama_olustur


@pytest.fixture(scope="function")
def izole_istemci(tmp_path: Path) -> Generator[TestClient, None, None]:
    """İzole SQLite veritabanı üzerinde çalışan TestClient örneği sağlar."""
    db_yolu = tmp_path / "gozlemlenebilirlik_test.db"
    ayarlar = Ayarlar(repo_tipi="sqlite", sqlite_db_path=str(db_yolu))
    konteyner = BagimlilikKonteyneri(ayarlar=ayarlar)
    app = uygulama_olustur(konteyner=konteyner)
    with TestClient(app) as istemci:
        yield istemci


class TestSistemGozlemlenebilirlik:
    """Yeni mühendislik konsolu uç noktalarını ve telemetri ara katmanını doğrular."""

    def test_statik_web_dosyalari_ve_sistem_telemetrisi(
        self, izole_istemci: TestClient
    ) -> None:
        ana_sayfa = izole_istemci.get("/")
        assert ana_sayfa.status_code == 200
        assert "Görev Yönetim Sistemi" in ana_sayfa.text
        assert "/static/styles.css" in ana_sayfa.text
        assert "/static/app.js" in ana_sayfa.text
        assert "no-store" in ana_sayfa.headers.get("cache-control", "")

        css = izole_istemci.get("/static/styles.css")
        assert css.status_code == 200
        assert "--bg-base" in css.text
        assert "no-store" in css.headers.get("cache-control", "")

        js = izole_istemci.get("/static/app.js")
        assert js.status_code == 200
        assert "kuralCanliTestEt" in js.text
        assert "hazirDemoCalistir" in js.text

        sistem = izole_istemci.get("/api/v1/sistem")
        assert sistem.status_code == 200
        veri = sistem.json()
        assert veri["aktif_repository"] == "sqlite"
        assert veri["depo_sinifi"] == "SqliteGorevRepository"
        assert veri["durum"] == "calisiyor"
        assert "X-Trace-Id" in sistem.headers
        assert "X-Process-Time-Ms" in sistem.headers

    def test_calisma_zamani_dip_depo_degisimi(
        self, izole_istemci: TestClient
    ) -> None:
        # 1. SQLite üzerinde görev oluştur
        sql_olustur = izole_istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "SQLite Kalıcı Görev", "oncelik": "YUKSEK"},
        )
        assert sql_olustur.status_code == 201
        assert sql_olustur.headers["X-Active-Repository"] == "sqlite"
        assert sql_olustur.headers["X-Active-Repo-Class"] == "SqliteGorevRepository"

        # 2. In-Memory adaptöre geç ve veri izolasyonunu doğrula
        memory_gecis = izole_istemci.post(
            "/api/v1/sistem/depo-degistir",
            json={"repo_tipi": "memory"},
        )
        assert memory_gecis.status_code == 200
        assert memory_gecis.json()["aktif_repository"] == "memory"
        assert memory_gecis.json()["depo_sinifi"] == "InMemoryGorevRepository"
        assert memory_gecis.json()["gorev_sayisi"] == 0

        mem_liste = izole_istemci.get("/api/v1/gorevler")
        assert mem_liste.status_code == 200
        assert mem_liste.json() == []

        # 3. Tekrar SQLite'a dön ve kaydın korunduğunu gör
        sql_donus = izole_istemci.post(
            "/api/v1/sistem/depo-degistir",
            json={"repo_tipi": "sqlite"},
        )
        assert sql_donus.status_code == 200
        assert sql_donus.json()["aktif_repository"] == "sqlite"
        assert sql_donus.json()["gorev_sayisi"] == 1

        # 4. Geçersiz repository isteği 400 dönmeli
        gecersiz = izole_istemci.post(
            "/api/v1/sistem/depo-degistir",
            json={"repo_tipi": "redis"},
        )
        assert gecersiz.status_code == 400
        assert gecersiz.json()["hata_kodu"] == "GECERSIZ_DEPO_TIPI"

    def test_canli_log_ve_domain_ihlali_izleme(
        self, izole_istemci: TestClient
    ) -> None:
        # Domain başlık hatası tetikle (422)
        baslik_hata = izole_istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "ab"},
        )
        assert baslik_hata.status_code == 422
        assert baslik_hata.headers["X-Domain-Exception"] == "GecersizBaslikHatasi"
        assert baslik_hata.headers["X-Domain-Error-Code"] == "GECERSIZ_BASLIK"

        # Kritik aktif görev silme koruması tetikle (400)
        kritik = izole_istemci.post(
            "/api/v1/gorevler",
            json={"baslik": "Kritik Koruma Görevi", "oncelik": "KRITIK"},
        ).json()
        izole_istemci.patch(
            f"/api/v1/gorevler/{kritik['id']}/durum",
            json={"yeni_durum": "DEVAM_EDIYOR"},
        )
        silme_red = izole_istemci.delete(f"/api/v1/gorevler/{kritik['id']}")
        assert silme_red.status_code == 400
        assert silme_red.headers["X-Domain-Exception"] == "KritikGorevSilinemezHatasi"

        # Loglarda Domain ihlallerinin katman zinciriyle göründüğünü doğrula
        ihlal_loglari = izole_istemci.get(
            "/api/v1/sistem/loglar",
            params={"seviye": "DOMAIN_IHLALI"},
        )
        assert ihlal_loglari.status_code == 200
        kayitlar = ihlal_loglari.json()["kayitlar"]
        assert len(kayitlar) >= 2

        en_son_ihlal = kayitlar[0]
        assert en_son_ihlal["hata_kodu"] == "KRITIK_GOREV_SILINEMEZ"
        katmanlar = {a["katman"]: a["durum"] for a in en_son_ihlal["katman_zinciri"]}
        assert katmanlar["Domain"] == "IHLAL"
        assert katmanlar["Infrastructure"] == "ATLANDI"

        # Log temizleme
        temizle = izole_istemci.delete("/api/v1/sistem/loglar")
        assert temizle.status_code == 200
        assert temizle.json()["silinen"] >= 1

    def test_canli_ast_mimari_denetimi_ve_kaynak_kod_korumasi(
        self, izole_istemci: TestClient
    ) -> None:
        ast_yaniti = izole_istemci.get("/api/v1/sistem/mimari-denetim")
        assert ast_yaniti.status_code == 200
        rapor = ast_yaniti.json()
        assert rapor["temiz"] is True
        assert rapor["toplam_ihlal"] == 0
        assert rapor["toplam_dosya"] >= 15
        assert {k["katman"] for k in rapor["katmanlar"]} == {
            "domain",
            "application",
            "infrastructure",
            "presentation",
        }
        assert all(k["durum"] == "TEMIZ" for k in rapor["katmanlar"])

        # İzinli dosya okuma
        kod_yanit = izole_istemci.get(
            "/api/v1/sistem/kaynak-kod",
            params={"dosya": "domain/entities/gorev.py"},
        )
        assert kod_yanit.status_code == 200
        assert kod_yanit.json()["katman"] == "domain"
        assert "class Gorev" in kod_yanit.json()["icerik"]

        # main.py okuma
        main_yanit = izole_istemci.get(
            "/api/v1/sistem/kaynak-kod",
            params={"dosya": "main.py"},
        )
        assert main_yanit.status_code == 200
        assert main_yanit.json()["katman"] == "composition_root"

        # Yol aşımı ve izin dışı dosyalar engellenmeli
        for yasak_yol in ["../Dockerfile", ".env", "baslat.bat", "tests/conftest.py"]:
            red = izole_istemci.get(
                "/api/v1/sistem/kaynak-kod",
                params={"dosya": yasak_yol},
            )
            assert red.status_code == 400
            assert red.json()["hata_kodu"] == "GECERSIZ_DOSYA_YOLU"

        olmayan = izole_istemci.get(
            "/api/v1/sistem/kaynak-kod",
            params={"dosya": "domain/olmayan_dosya.py"},
        )
        assert olmayan.status_code == 404
        assert olmayan.json()["hata_kodu"] == "DOSYA_BULUNAMADI"

    def test_ornek_veri_yukleme_tum_durumlari_kapsamali(
        self, izole_istemci: TestClient
    ) -> None:
        yanit = izole_istemci.post("/api/v1/sistem/ornek-veri-yukle")
        assert yanit.status_code == 201
        veri = yanit.json()
        assert veri["eklenen_sayisi"] == 5
        durumlar = {g["durum"] for g in veri["gorevler"]}
        assert durumlar == {"BEKLEMEDE", "DEVAM_EDIYOR", "TAMAMLANDI", "IPTAL_EDILDI"}

    def test_mimari_kokpit_yeni_uc_noktalari(
        self, izole_istemci: TestClient
    ) -> None:
        ozet = izole_istemci.get("/api/v1/mimari/ozet")
        assert ozet.status_code == 200
        ozet_veri = ozet.json()
        assert ozet_veri["aktif_repository"] == "sqlite"
        assert len(ozet_veri["durum_matrisi"]) == 16
        assert len(ozet_veri["is_kurallari"]) == 5
        assert len(ozet_veri["solid_prensipleri"]) == 5
        assert len(ozet_veri["depo_karsilastirma"]) == 2
        assert ozet_veri["test_ozeti"]["test_fonksiyonu"] >= 20

        ast_yaniti = izole_istemci.get("/api/v1/mimari/ast-denetim")
        assert ast_yaniti.status_code == 200
        assert ast_yaniti.json()["temiz"] is True
        assert ast_yaniti.json()["toplam_ihlal"] == 0

        izole_istemci.post("/api/v1/gorevler", json={"baslik": "Mimari İz Test Görevi"})
        izler = izole_istemci.get("/api/v1/mimari/izler")
        assert izler.status_code == 200
        assert izler.json()["toplam_kayit"] >= 2

        kod = izole_istemci.get(
            "/api/v1/mimari/kaynak-kod",
            params={"dosya": "domain/entities/gorev.py"},
        )
        assert kod.status_code == 200
        assert "class Gorev" in kod.json()["icerik"]

        red = izole_istemci.get(
            "/api/v1/mimari/kaynak-kod",
            params={"dosya": "../Dockerfile"},
        )
        assert red.status_code == 400
        assert red.json()["hata_kodu"] == "GECERSIZ_DOSYA_YOLU"
