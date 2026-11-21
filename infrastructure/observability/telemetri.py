"""Gerçek zamanlı işlem telemetrisi, AST bağımlılık denetimi ve salt okunur kod okuyucu."""

from __future__ import annotations

import ast
import sys
import time
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Optional

KATMANLAR: tuple[str, ...] = (
    "domain",
    "application",
    "infrastructure",
    "presentation",
)

IZINLI_KOD_KOKLERI: frozenset[str] = frozenset(KATMANLAR)

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

_KATMAN_KURAL_ACIKLAMALARI: dict[str, str] = {
    "domain": "Yalnızca domain ve Python standart kütüphanesi (sıfır dış bağımlılık).",
    "application": "Yalnızca application, domain ve Python standart kütüphanesi.",
    "infrastructure": "domain / application sözleşmelerini uygular; presentation'a bağlanmaz.",
    "presentation": "API / UI sunum katmanı; application DTO ve use-case'leri ile konuşur.",
}


@dataclass(frozen=True)
class IslemKaydi:
    """Tek bir API isteğinin katmanlar arası gerçek çalışma izini temsil eder."""

    iz_id: str
    zaman: str
    metot: str
    yol: str
    durum_kodu: int
    sure_ms: float
    seviye: str
    aktif_repository: str
    depo_sinifi: str
    use_case: str
    katman_zinciri: list[dict[str, str]] = field(default_factory=list)
    hata_kodu: Optional[str] = None
    hata_sinifi: Optional[str] = None
    kaynak_dosya: Optional[str] = None
    mesaj: str = ""
    istek_govdesi: Any = None
    yanit_ozeti: Any = None

    def sozluge_cevir(self) -> dict[str, Any]:
        """Kayıt verisini JSON serileştirmeye uygun sözlüğe dönüştürür."""
        return asdict(self)


class IslemKayitDefteri:
    """Son API işlemlerini ve katman ihlallerini bellek içi halkasal tamponda saklar."""

    def __init__(self, maks_kayit: int = 250) -> None:
        self._kilit: RLock = RLock()
        self._kayitlar: deque[IslemKaydi] = deque(maxlen=maks_kayit)
        self._baslangic_monotonic: float = time.monotonic()
        self._baslangic_zamani: str = datetime.now(timezone.utc).isoformat()
        self._toplam_istek: int = 0
        self._basarili_istek: int = 0
        self._domain_ihlal_sayisi: int = 0

    def istek_istatistigi_isle(self, durum_kodu: int, domain_ihlali: bool = False) -> None:
        """Pasif uç noktalar dahil hafif sayaç güncellemeleri için kullanılır."""
        with self._kilit:
            self._toplam_istek += 1
            if domain_ihlali:
                self._domain_ihlal_sayisi += 1
            elif 200 <= durum_kodu < 400:
                self._basarili_istek += 1

    def kayit_ekle(self, kayit: IslemKaydi) -> None:
        """Yeni bir işlem kaydını tampona ekler ve sayaçları günceller."""
        with self._kilit:
            self._kayitlar.appendleft(kayit)
            self._toplam_istek += 1
            if kayit.seviye == "DOMAIN_IHLALI":
                self._domain_ihlal_sayisi += 1
            elif 200 <= kayit.durum_kodu < 400:
                self._basarili_istek += 1

    def listele(
        self,
        seviye: Optional[str] = None,
        limit: int = 100,
    ) -> list[IslemKaydi]:
        """İstenen seviyeye göre en yeniden eskiye doğru kayıtları döndürür."""
        sinir = max(1, min(limit, 250))
        with self._kilit:
            if seviye:
                hedef = seviye.strip().upper()
                filtrelenmis = [k for k in self._kayitlar if k.seviye == hedef]
            else:
                filtrelenmis = list(self._kayitlar)
            return filtrelenmis[:sinir]

    def temizle(self) -> int:
        """Tampondaki tüm kayıtları temizler ve silinen kayıt sayısını döndürür."""
        with self._kilit:
            sayi = len(self._kayitlar)
            self._kayitlar.clear()
            return sayi

    def ozet(self) -> dict[str, Any]:
        """Anlık telemetri özet metriklerini döndürür."""
        with self._kilit:
            return {
                "calisma_suresi_sn": round(
                    time.monotonic() - self._baslangic_monotonic, 1
                ),
                "toplam_istek": self._toplam_istek,
                "basarili_istek": self._basarili_istek,
                "domain_ihlal_sayisi": self._domain_ihlal_sayisi,
                "baslangic_zamani": self._baslangic_zamani,
                "kayit_sayisi": len(self._kayitlar),
            }


def _ast_import_ve_yapilari_cikar(
    dosya_yolu: Path,
    proje_koku: Path,
) -> tuple[set[str], list[str], list[str], int]:
    """Bir Python dosyasından kök importları, sınıf/fonksiyon adlarını ve satır sayısını çıkarır."""
    kaynak = dosya_yolu.read_text(encoding="utf-8")
    satir_sayisi = len(kaynak.splitlines())
    agac = ast.parse(kaynak, filename=str(dosya_yolu))

    importlar: set[str] = set()
    siniflar: list[str] = []
    fonksiyonlar: list[str] = []

    for dugum in agac.body:
        if isinstance(dugum, ast.ClassDef):
            siniflar.append(dugum.name)
        elif isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fonksiyonlar.append(dugum.name)

    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Import):
            for takma_ad in dugum.names:
                importlar.add(takma_ad.name.split(".")[0])
        elif isinstance(dugum, ast.ImportFrom):
            if dugum.level > 0:
                goreli_parcalar = dosya_yolu.relative_to(proje_koku).parts[:-1]
                if dugum.level > len(goreli_parcalar):
                    importlar.add("__ust_dizin_kacisi__")
                elif goreli_parcalar:
                    importlar.add(goreli_parcalar[0])
            elif dugum.module:
                importlar.add(dugum.module.split(".")[0])

    return importlar, siniflar, fonksiyonlar, satir_sayisi


def ast_mimari_denetimi_calistir(proje_koku: Path) -> dict[str, Any]:
    """Projedeki tüm Python dosyalarını AST ile tarayarak Clean Architecture kurallarını doğrular."""
    baslangic = time.perf_counter()
    kok = proje_koku.resolve()

    dosya_sonuclari: list[dict[str, Any]] = []
    katman_ozetleri: list[dict[str, Any]] = []
    kenar_sayaci: Counter[tuple[str, str]] = Counter()
    toplam_satir = 0
    toplam_ihlal = 0

    for katman in KATMANLAR:
        katman_dizini = kok / katman
        if not katman_dizini.is_dir():
            katman_ozetleri.append(
                {
                    "katman": katman,
                    "dosya_sayisi": 0,
                    "satir_sayisi": 0,
                    "ihlal_sayisi": 1,
                    "kural": _KATMAN_KURAL_ACIKLAMALARI[katman],
                    "durum": "IHLAL",
                }
            )
            toplam_ihlal += 1
            continue

        py_dosyalari = sorted(katman_dizini.rglob("*.py"))
        katman_satir = 0
        katman_ihlal = 0

        for dosya in py_dosyalari:
            goreli_yol = dosya.relative_to(kok).as_posix()
            importlar, siniflar, fonksiyonlar, satir_sayisi = _ast_import_ve_yapilari_cikar(
                dosya, kok
            )
            katman_satir += satir_sayisi
            toplam_satir += satir_sayisi

            ic_importlar = sorted(m for m in importlar if m in IZINLI_KOD_KOKLERI)
            stdlib_importlar = sorted(
                m for m in importlar if m in sys.stdlib_module_names and m not in IZINLI_KOD_KOKLERI
            )
            dis_importlar = sorted(
                m
                for m in importlar
                if m not in IZINLI_KOD_KOKLERI and m not in sys.stdlib_module_names
            )

            for hedef_katman in ic_importlar:
                if hedef_katman != katman:
                    kenar_sayaci[(katman, hedef_katman)] += 1

            ihlaller: list[str] = []
            if katman == "domain":
                yasak = sorted(importlar & DOMAIN_YASAKLI_MODULLER)
                if yasak:
                    ihlaller.append(f"Yasaklı modül importu: {', '.join(yasak)}")
                if dis_importlar:
                    ihlaller.append(f"Standart dışı dış kütüphane: {', '.join(dis_importlar)}")
            elif katman == "application":
                yasak = sorted(importlar & APPLICATION_YASAKLI_MODULLER)
                if yasak:
                    ihlaller.append(f"Yasaklı modül importu: {', '.join(yasak)}")
                if dis_importlar:
                    ihlaller.append(f"Standart dışı dış kütüphane: {', '.join(dis_importlar)}")
            elif katman == "infrastructure":
                if "presentation" in importlar:
                    ihlaller.append("Infrastructure katmanı presentation'ı import edemez.")

            katman_ihlal += len(ihlaller)
            toplam_ihlal += len(ihlaller)

            dosya_sonuclari.append(
                {
                    "dosya": goreli_yol,
                    "katman": katman,
                    "satir_sayisi": satir_sayisi,
                    "siniflar": siniflar,
                    "fonksiyonlar": fonksiyonlar,
                    "ic_importlar": ic_importlar,
                    "stdlib_importlar": stdlib_importlar,
                    "dis_importlar": dis_importlar,
                    "ihlaller": ihlaller,
                    "temiz": len(ihlaller) == 0,
                }
            )

        katman_ozetleri.append(
            {
                "katman": katman,
                "dosya_sayisi": len(py_dosyalari),
                "satir_sayisi": katman_satir,
                "ihlal_sayisi": katman_ihlal,
                "kural": _KATMAN_KURAL_ACIKLAMALARI[katman],
                "durum": "TEMIZ" if katman_ihlal == 0 else "IHLAL",
            }
        )

    kenarlar = [
        {"kaynak": k, "hedef": h, "sayac": s}
        for (k, h), s in sorted(kenar_sayaci.items())
    ]

    return {
        "temiz": toplam_ihlal == 0,
        "toplam_dosya": len(dosya_sonuclari),
        "toplam_satir": toplam_satir,
        "toplam_ihlal": toplam_ihlal,
        "sure_ms": round((time.perf_counter() - baslangic) * 1000, 2),
        "katmanlar": katman_ozetleri,
        "kenarlar": kenarlar,
        "dosyalar": dosya_sonuclari,
    }


def kaynak_kod_oku(proje_koku: Path, goreli_yol: str) -> dict[str, Any]:
    """Yalnızca izin verilen uygulama katmanlarındaki Python dosyalarını salt okunur döndürür."""
    if not isinstance(goreli_yol, str) or not goreli_yol.strip():
        raise ValueError("Dosya yolu boş olamaz.")

    temiz_yol = goreli_yol.strip().replace("\\", "/")
    if temiz_yol.startswith("/") or ":" in temiz_yol.split("/")[0]:
        raise ValueError("Mutlak dosya yollarına izin verilmez.")

    parcalar = [p for p in temiz_yol.split("/") if p]
    if not parcalar or ".." in parcalar or "." in parcalar:
        raise ValueError("Geçersiz göreli dosya yolu.")

    if not temiz_yol.endswith(".py"):
        raise ValueError("Yalnızca Python (.py) kaynak dosyaları incelenebilir.")

    if temiz_yol != "main.py" and parcalar[0] not in IZINLI_KOD_KOKLERI:
        raise ValueError(
            "Yalnızca domain, application, infrastructure, presentation veya main.py dosyaları okunabilir."
        )

    kok = proje_koku.resolve()
    hedef = (kok / Path(*parcalar)).resolve()
    if not hedef.is_relative_to(kok):
        raise ValueError("Proje dizini dışına erişim engellendi.")
    if not hedef.is_file():
        raise FileNotFoundError(f"'{temiz_yol}' dosyası bulunamadı.")

    icerik = hedef.read_text(encoding="utf-8")
    katman = "composition_root" if temiz_yol == "main.py" else parcalar[0]
    return {
        "dosya": "/".join(parcalar),
        "katman": katman,
        "satir_sayisi": len(icerik.splitlines()),
        "icerik": icerik,
    }


def test_sayisini_hesapla(proje_koku: Path) -> dict[str, int]:
    """AST ile tests dizinindeki test dosyası ve test fonksiyonu sayılarını hesaplar."""
    test_koku = proje_koku.resolve() / "tests"
    sayac: dict[str, int] = {
        "test_dosyasi": 0,
        "test_fonksiyonu": 0,
        "mimari_test": 0,
        "birim_test": 0,
        "entegrasyon_test": 0,
    }
    if not test_koku.is_dir():
        return sayac

    for dosya in sorted(test_koku.rglob("test_*.py")):
        sayac["test_dosyasi"] += 1
        agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
        fonk_sayisi = sum(
            1
            for dugum in ast.walk(agac)
            if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef))
            and dugum.name.startswith("test_")
        )
        sayac["test_fonksiyonu"] += fonk_sayisi
        goreli = dosya.relative_to(test_koku).parts
        alt_klasor = goreli[0] if len(goreli) > 1 else ""
        if alt_klasor == "architecture":
            sayac["mimari_test"] += fonk_sayisi
        elif alt_klasor == "unit":
            sayac["birim_test"] += fonk_sayisi
        elif alt_klasor == "integration":
            sayac["entegrasyon_test"] += fonk_sayisi

    return sayac
