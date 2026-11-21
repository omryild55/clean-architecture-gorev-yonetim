"""Clean Architecture Bağımlılık Kuralı (Dependency Rule) AST denetim testleri."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJE_KOKU: Path = Path(__file__).resolve().parents[2]

DOMAIN_YASAKLI_MODULLER: frozenset[str] = frozenset(
    {
        "application",
        "infrastructure",
        "presentation",
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "starlette",
        "uvicorn",
        "main",
        "pytest",
        "httpx",
        "tests",
    }
)

APPLICATION_YASAKLI_MODULLER: frozenset[str] = frozenset(
    {
        "infrastructure",
        "presentation",
        "fastapi",
        "sqlalchemy",
        "pydantic",
        "starlette",
        "uvicorn",
        "main",
        "pytest",
        "httpx",
        "tests",
    }
)


def _katman_dosyalarini_bul(katman_adi: str) -> list[Path]:
    katman_dizini = PROJE_KOKU / katman_adi
    assert katman_dizini.is_dir(), f"'{katman_adi}' klasörü bulunamadı."
    dosyalar = sorted(katman_dizini.rglob("*.py"))
    assert dosyalar, f"'{katman_adi}' klasöründe hiç Python dosyası bulunamadı."
    return dosyalar


def _ust_paket_importlarini_cikar(dosya_yolu: Path) -> set[str]:
    """Bir Python dosyasındaki tüm import kök modül adlarını AST ile çıkarır."""
    kaynak = dosya_yolu.read_text(encoding="utf-8")
    agac = ast.parse(kaynak, filename=str(dosya_yolu))
    importlar: set[str] = set()

    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            for takma_ad in dugum.names:
                importlar.add(takma_ad.name.split(".")[0])
        elif isinstance(dugum, ast.ImportFrom):
            if dugum.level > 0:
                goreli_parcalar = dosya_yolu.relative_to(PROJE_KOKU).parts[:-1]
                if dugum.level > len(goreli_parcalar):
                    importlar.add("__ust_dizin_kacisi__")
                else:
                    hedef_kok = goreli_parcalar[0]
                    importlar.add(hedef_kok)
            elif dugum.module:
                importlar.add(dugum.module.split(".")[0])

    return importlar


class TestCleanArchitectureBagimlilikKurallari:
    """İç halkaların dış halkaları veya çerçeveleri import etmediğini AST ile doğrular."""

    def test_domain_katmani_sifir_dis_bagimlilik_icermeli(self) -> None:
        domain_dosyalari = _katman_dosyalarini_bul("domain")

        for dosya in domain_dosyalari:
            importlar = _ust_paket_importlarini_cikar(dosya)
            yasakli_ihlal = importlar & DOMAIN_YASAKLI_MODULLER
            assert not yasakli_ihlal, (
                f"Mimari İhlal! {dosya.relative_to(PROJE_KOKU)} dosyası yasaklı "
                f"modülleri import ediyor: {sorted(yasakli_ihlal)}"
            )

            dis_kutuphaneler = importlar - {"domain"} - sys.stdlib_module_names
            assert not dis_kutuphaneler, (
                f"Mimari İhlal! {dosya.relative_to(PROJE_KOKU)} dosyası Python "
                f"standart kütüphanesi dışında paket import ediyor: "
                f"{sorted(dis_kutuphaneler)}"
            )

    def test_application_katmani_dis_katmanlara_ve_frameworklere_baglanmamali(
        self,
    ) -> None:
        app_dosyalari = _katman_dosyalarini_bul("application")

        for dosya in app_dosyalari:
            importlar = _ust_paket_importlarini_cikar(dosya)
            yasakli_ihlal = importlar & APPLICATION_YASAKLI_MODULLER
            assert not yasakli_ihlal, (
                f"Mimari İhlal! {dosya.relative_to(PROJE_KOKU)} dosyası dış katman "
                f"veya çerçeve import ediyor: {sorted(yasakli_ihlal)}"
            )

            dis_kutuphaneler = (
                importlar - {"application", "domain"} - sys.stdlib_module_names
            )
            assert not dis_kutuphaneler, (
                f"Mimari İhlal! {dosya.relative_to(PROJE_KOKU)} dosyası izin "
                f"verilmeyen dış paket import ediyor: {sorted(dis_kutuphaneler)}"
            )
