"""Mimari telemetri, canlı AST bağımlılık taraması ve gözlem kokpiti salt-okunur API uç noktaları."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse

from domain.value_objects.gorev_durumu import GorevDurumu
from infrastructure.config.ayarlar import BagimlilikKonteyneri
from infrastructure.observability.telemetri import (
    ast_mimari_denetimi_calistir,
    kaynak_kod_oku,
    test_sayisini_hesapla,
)
from presentation.api.gorev_router import (
    PROJE_KOKU,
    _kayit_defterini_al,
    _konteyneri_al,
)
from presentation.api.semalar import (
    DurumGecisHucresiYaniti,
    HataYaniti,
    IslemLoguYaniti,
    KatmanAdimiYaniti,
    KaynakKodYaniti,
    LogListesiYaniti,
    MimariDenetimYaniti,
    MimariOzetYaniti,
)

mimari_router = APIRouter(
    prefix="/api/v1/mimari",
    tags=["Mimari & Gözlem"],
)

_IS_KURALLARI_OZETI: list[dict[str, Any]] = [
    {
        "kural_no": 1,
        "baslik": "Geçmiş Bitiş Tarihi Engeli",
        "hata_sinifi": "GecmisTarihHatasi",
        "hata_kodu": "GECMIS_TARIH",
        "http_kod": 422,
        "dosya": "domain/value_objects/tarih_dogrulama.py",
        "aciklama": "Bitiş tarihi bugünden/şu andan geçmişte olamaz; UTC normalize edilir.",
    },
    {
        "kural_no": 2,
        "baslik": "Durum Makinesi Geçiş Denetimi",
        "hata_sinifi": "GecersizDurumGecisiHatasi",
        "hata_kodu": "GECERSIZ_DURUM_GECISI",
        "http_kod": 400,
        "dosya": "domain/entities/gorev.py",
        "aciklama": "BEKLEMEDE doğrudan TAMAMLANDI olamaz; IPTAL_EDILDI görev yeniden başlatılamaz.",
    },
    {
        "kural_no": 3,
        "baslik": "Tamamlanmış Görev Salt Okunur Kilidi",
        "hata_sinifi": "KilitliGorevHatasi",
        "hata_kodu": "KILITLI_GOREV",
        "http_kod": 400,
        "dosya": "domain/entities/gorev.py",
        "aciklama": "TAMAMLANDI durumundaki görevin alanları değiştirilemez (PUT 400).",
    },
    {
        "kural_no": 4,
        "baslik": "Kritik Aktif Görev Silme Koruması",
        "hata_sinifi": "KritikGorevSilinemezHatasi",
        "hata_kodu": "KRITIK_GOREV_SILINEMEZ",
        "http_kod": 400,
        "dosya": "domain/entities/gorev.py",
        "aciklama": "Önceliği KRITIK ve durumu DEVAM_EDIYOR olan görev doğrudan silinemez.",
    },
    {
        "kural_no": 5,
        "baslik": "Başlık Karakter Sınırı ve Kırpma",
        "hata_sinifi": "GecersizBaslikHatasi",
        "hata_kodu": "GECERSIZ_BASLIK",
        "http_kod": 422,
        "dosya": "domain/value_objects/tarih_dogrulama.py",
        "aciklama": "GorevBasligi değer nesnesi başlığı kırpar ve 3-100 karakter şartını korur.",
    },
]

_SOLID_OZETI: list[dict[str, Any]] = [
    {
        "harf": "S",
        "ilke": "Single Responsibility",
        "bilesen": "Gorev Entity vs FastAPI Router",
        "dosya": "domain/entities/gorev.py",
        "aciklama": "İş kuralları yalnızca Domain içinde, HTTP serileştirme Presentation içinde yer alır.",
    },
    {
        "harf": "O",
        "ilke": "Open / Closed",
        "bilesen": "BagimlilikKonteyneri",
        "dosya": "infrastructure/config/ayarlar.py",
        "aciklama": "Yeni kalıcılık adaptörü eklemek çekirdek Domain/Application kodunu değiştirmez.",
    },
    {
        "harf": "L",
        "ilke": "Liskov Substitution",
        "bilesen": "Sqlite & InMemory Repository",
        "dosya": "infrastructure/persistence/sqlite_gorev_repository.py",
        "aciklama": "İki adaptör aynı iş kuralları ve arama semantiğiyle yer değiştirebilir.",
    },
    {
        "harf": "I",
        "ilke": "Interface Segregation",
        "bilesen": "GorevRepositoryArayuzu",
        "dosya": "domain/repositories/gorev_repository_arayuzu.py",
        "aciklama": "Yalnızca gerekli 5 atomik metot tanımlı odaklanmış soyut sözleşme.",
    },
    {
        "harf": "D",
        "ilke": "Dependency Inversion",
        "bilesen": "UseCase -> ABC Port",
        "dosya": "application/use_cases/gorev_olustur.py",
        "aciklama": "Yüksek seviyeli Use Case sınıfları somut veritabanına değil soyut arayüze bağlıdır.",
    },
]

_KATMAN_HARITASI: list[dict[str, Any]] = [
    {
        "katman": "domain",
        "baslik": "1. Domain (Çekirdek İş Kuralları)",
        "yol": "domain/",
        "alt_dizinler": ["entities/", "value_objects/", "exceptions/", "repositories/"],
        "bagimlilik": "Yalnızca Python stdlib (sıfır dış paket).",
    },
    {
        "katman": "application",
        "baslik": "2. Application (Kullanım Senaryoları)",
        "yol": "application/",
        "alt_dizinler": ["dtos/", "use_cases/"],
        "bagimlilik": "Yalnızca domain ve Python stdlib.",
    },
    {
        "katman": "infrastructure",
        "baslik": "3. Infrastructure (Altyapı & Adaptörler)",
        "yol": "infrastructure/",
        "alt_dizinler": ["persistence/", "config/", "observability/"],
        "bagimlilik": "SQLAlchemy, DI Konteyner, Telemetri & AST Denetçi.",
    },
    {
        "katman": "presentation",
        "baslik": "4. Presentation (API & Gözlem Kokpiti)",
        "yol": "presentation/",
        "alt_dizinler": ["api/", "web/"],
        "bagimlilik": "FastAPI, Pydantic, Global Handler, Vanilla JS Kokpit.",
    },
]


def _gecis_kurali_aciklamasi(kaynak: GorevDurumu, hedef: GorevDurumu, izinli: bool) -> str:
    """Durum makinesi matrisi hücresi için anlaşılır Türkçe kural açıklaması döndürür."""
    if kaynak == hedef:
        return "Aynı duruma geçiş yasaktır; varlık zaten bu durumdadır."
    if kaynak == GorevDurumu.BEKLEMEDE and hedef == GorevDurumu.TAMAMLANDI:
        return "Yasak (Kural 2): BEKLEMEDE doğrudan TAMAMLANDI olamaz; DEVAM_EDIYOR gerekir."
    if kaynak == GorevDurumu.TAMAMLANDI:
        return "Yasak (Kural 3): TAMAMLANDI terminal durumdur; değiştirilemez."
    if kaynak == GorevDurumu.IPTAL_EDILDI:
        return "Yasak (Kural 2): IPTAL_EDILDI terminal durumdur; yeniden başlatılamaz."
    if izinli:
        return f"İzinli geçiş: {kaynak.value} -> {hedef.value} durum makinesine uygundur."
    return "Geçersiz geçiş."


@mimari_router.get(
    "/ozet",
    response_model=MimariOzetYaniti,
    status_code=status.HTTP_200_OK,
    summary="Mimari kokpit için durum matrisi, test sayıları, SOLID ve depo karşılaştırması",
)
def mimari_ozet_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> MimariOzetYaniti:
    """Domain durum makinesini, test kapsamını ve LSP adaptör bilgilerini salt-okunur döndürür."""
    aktif_tip = konteyner.aktif_repo_tipi
    veritabani_yolu = (
        ":memory:" if aktif_tip == "memory" else konteyner.ayarlar.sqlite_db_path
    )

    matris: list[DurumGecisHucresiYaniti] = []
    for kaynak in GorevDurumu:
        for hedef in GorevDurumu:
            izinli = kaynak.gecis_yapilabilir_mi(hedef)
            matris.append(
                DurumGecisHucresiYaniti(
                    kaynak=kaynak.value,
                    hedef=hedef.value,
                    izinli=izinli,
                    kural_aciklamasi=_gecis_kurali_aciklamasi(kaynak, hedef, izinli),
                )
            )

    depo_karsilastirma = [
        {
            "repo_tipi": "sqlite",
            "sinif": "SqliteGorevRepository",
            "aktif": aktif_tip == "sqlite",
            "sozlesme": "GorevRepositoryArayuzu",
            "mekanizma": "SQLAlchemy 2.0 ORM + UTC Normalize + Casefold Arama",
            "kalicilik": f"Disk SQLite ({konteyner.ayarlar.sqlite_db_path})",
            "es_zamanlilik": "Session kapsamlı işlem bütünlüğü + kapat() engine temizliği",
        },
        {
            "repo_tipi": "memory",
            "sinif": "InMemoryGorevRepository",
            "aktif": aktif_tip == "memory",
            "sozlesme": "GorevRepositoryArayuzu",
            "mekanizma": "Python dict + kopyala() yalıtımı + Casefold Arama",
            "kalicilik": "RAM İçi Geçici Bellek (Sıfır G/Ç)",
            "es_zamanlilik": "threading.RLock ile iş parçacığı güvenli erişim",
        },
    ]

    return MimariOzetYaniti(
        aktif_repository=aktif_tip,
        depo_sinifi=konteyner.aktif_depo_sinifi,
        veritabani_yolu=veritabani_yolu,
        test_ozeti=test_sayisini_hesapla(PROJE_KOKU),
        durum_matrisi=matris,
        is_kurallari=_IS_KURALLARI_OZETI,
        solid_prensipleri=_SOLID_OZETI,
        katman_haritasi=_KATMAN_HARITASI,
        depo_karsilastirma=depo_karsilastirma,
    )


@mimari_router.get(
    "/ast-denetim",
    response_model=MimariDenetimYaniti,
    status_code=status.HTTP_200_OK,
    summary="Canlı AST katman bağımlılığı taramasını çalıştır",
)
def mimari_ast_denetimi_getir(request: Request) -> MimariDenetimYaniti:
    """Domain ve Application katmanlarının sıfır dış bağımlılık kuralını canlı AST ile doğrular."""
    request.state.use_case = "AST.MimariDenetim"
    rapor: dict[str, Any] = ast_mimari_denetimi_calistir(PROJE_KOKU)
    request.state.yanit_ozeti = {
        "temiz": rapor["temiz"],
        "toplam_dosya": rapor["toplam_dosya"],
        "toplam_satir": rapor["toplam_satir"],
        "toplam_ihlal": rapor["toplam_ihlal"],
    }
    return MimariDenetimYaniti(**rapor)


@mimari_router.get(
    "/izler",
    response_model=LogListesiYaniti,
    status_code=status.HTTP_200_OK,
    summary="Katman yürütme izlerini ve HTTP/JSON loglarını getir",
)
def mimari_izleri_getir(
    request: Request,
    seviye: Optional[str] = Query(
        default=None, description="Filtre seviyesi (BASARILI, DOMAIN_IHLALI, HATA)"
    ),
    limit: int = Query(default=120, ge=1, le=250, description="Maksimum kayıt sayısı"),
) -> LogListesiYaniti:
    """İsteklerin katman geçiş izlerini ve JSON özetlerini döndürür."""
    defter = _kayit_defterini_al(request)
    kayitlar = defter.listele(seviye=seviye, limit=limit)
    donusturulmus = [
        IslemLoguYaniti(
            iz_id=k.iz_id,
            zaman=k.zaman,
            metot=k.metot,
            yol=k.yol,
            durum_kodu=k.durum_kodu,
            sure_ms=k.sure_ms,
            seviye=k.seviye,
            aktif_repository=k.aktif_repository,
            depo_sinifi=k.depo_sinifi,
            use_case=k.use_case,
            katman_zinciri=[
                KatmanAdimiYaniti(**adim) for adim in k.katman_zinciri
            ],
            hata_kodu=k.hata_kodu,
            hata_sinifi=k.hata_sinifi,
            kaynak_dosya=k.kaynak_dosya,
            mesaj=k.mesaj,
            istek_govdesi=k.istek_govdesi,
            yanit_ozeti=k.yanit_ozeti,
        )
        for k in kayitlar
    ]
    return LogListesiYaniti(
        toplam_kayit=len(donusturulmus),
        ozet=defter.ozet(),
        kayitlar=donusturulmus,
    )


@mimari_router.get(
    "/kaynak-kod",
    response_model=KaynakKodYaniti,
    status_code=status.HTTP_200_OK,
    summary="İzinli mimari kaynak dosyalarının kodunu salt-okunur getir",
)
def mimari_kaynak_kod_getir(
    dosya: str = Query(..., description="Görevi Python dosya yolu"),
) -> Response:
    """Clean Architecture katmanlarındaki Python dosyalarını güvenli şekilde döndürür."""
    try:
        veri = kaynak_kod_oku(PROJE_KOKU, dosya)
    except ValueError as hata:
        icerik = HataYaniti(
            hata_kodu="GECERSIZ_DOSYA_YOLU",
            mesaj=str(hata),
            durum_kodu=status.HTTP_400_BAD_REQUEST,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=icerik.model_dump(),
        )
    except FileNotFoundError as hata:
        icerik = HataYaniti(
            hata_kodu="DOSYA_BULUNAMADI",
            mesaj=str(hata),
            durum_kodu=status.HTTP_404_NOT_FOUND,
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=icerik.model_dump(),
        )

    yanit = KaynakKodYaniti(**veri)
    return JSONResponse(status_code=status.HTTP_200_OK, content=yanit.model_dump())
