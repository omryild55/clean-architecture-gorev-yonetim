"""FastAPI RESTful uç noktaları, sistem gözlemlenebilirliği ve Global Domain Exception Handler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse

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
    DomainHatasi,
    GecersizBaslikHatasi,
    GecersizDurumGecisiHatasi,
    GecmisTarihHatasi,
    GorevBulunamadiHatasi,
    KilitliGorevHatasi,
    KritikGorevSilinemezHatasi,
)
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi
from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri
from infrastructure.observability.telemetri import (
    IslemKayitDefteri,
    ast_mimari_denetimi_calistir,
    kaynak_kod_oku,
)
from presentation.api.semalar import (
    DepoDegistirIstegi,
    DepoDegistirYaniti,
    GorevDurumDegistirIstegi,
    GorevGuncelleIstegi,
    GorevOlusturIstegi,
    GorevYaniti,
    HataYaniti,
    IslemLoguYaniti,
    KatmanAdimiYaniti,
    KaynakKodYaniti,
    LogListesiYaniti,
    LogTemizleYaniti,
    MimariDenetimYaniti,
    OrnekVeriYaniti,
    SistemBilgisiYaniti,
)

PROJE_KOKU: Path = Path(__file__).resolve().parents[2]

_DOMAIN_HTTP_ESLEMESI: dict[type[DomainHatasi], int] = {
    GorevBulunamadiHatasi: status.HTTP_404_NOT_FOUND,
    GecersizBaslikHatasi: status.HTTP_422_UNPROCESSABLE_CONTENT,
    GecmisTarihHatasi: status.HTTP_422_UNPROCESSABLE_CONTENT,
    GecersizDurumGecisiHatasi: status.HTTP_400_BAD_REQUEST,
    KilitliGorevHatasi: status.HTTP_400_BAD_REQUEST,
    KritikGorevSilinemezHatasi: status.HTTP_400_BAD_REQUEST,
}

_DOMAIN_KAYNAK_ESLEMESI: dict[type[DomainHatasi], str] = {
    GorevBulunamadiHatasi: "domain/exceptions/domain_hatalari.py",
    GecersizBaslikHatasi: "domain/value_objects/tarih_dogrulama.py",
    GecmisTarihHatasi: "domain/value_objects/tarih_dogrulama.py",
    GecersizDurumGecisiHatasi: "domain/entities/gorev.py",
    KilitliGorevHatasi: "domain/entities/gorev.py",
    KritikGorevSilinemezHatasi: "domain/entities/gorev.py",
}

gorev_router = APIRouter(
    prefix="/api/v1/gorevler",
    tags=["Görevler"],
    responses={
        400: {"model": HataYaniti, "description": "İş kuralı / durum makinesi ihlali"},
        404: {"model": HataYaniti, "description": "Görev bulunamadı"},
        422: {"model": HataYaniti, "description": "Doğrulama / geçmiş tarih hatası"},
    },
)

sistem_router = APIRouter(
    prefix="/api/v1/sistem",
    tags=["Sistem"],
)


def _konteyneri_al(request: Request) -> BagimlilikKonteyneri:
    """Uygulama durumundan (app.state) DI konteynerini çözümler; yoksa tembel oluşturur."""
    konteyner: Optional[BagimlilikKonteyneri] = getattr(
        request.app.state, "konteyner", None
    )
    if konteyner is None:
        ayarlar: Optional[Ayarlar] = getattr(request.app.state, "ayarlar", None)
        konteyner = BagimlilikKonteyneri(ayarlar=ayarlar)
        request.app.state.konteyner = konteyner
    return konteyner


def _kayit_defterini_al(request: Request) -> IslemKayitDefteri:
    """Uygulama durumundan işlem telemetri kayıt defterini döndürür; yoksa oluşturur."""
    defter: Optional[IslemKayitDefteri] = getattr(
        request.app.state, "kayit_defteri", None
    )
    if defter is None:
        defter = IslemKayitDefteri()
        request.app.state.kayit_defteri = defter
    return defter


def olustur_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevOlusturUseCase:
    """GorevOlusturUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_olustur_use_case()


def listele_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevListeleUseCase:
    """GorevListeleUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_listele_use_case()


def getir_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevGetirUseCase:
    """GorevGetirUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_getir_use_case()


def guncelle_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevGuncelleUseCase:
    """GorevGuncelleUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_guncelle_use_case()


def durum_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevDurumDegistirUseCase:
    """GorevDurumDegistirUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_durum_degistir_use_case()


def sil_uc_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> GorevSilUseCase:
    """GorevSilUseCase bağımlılık sağlayıcısı."""
    return konteyner.gorev_sil_use_case()


@gorev_router.post(
    "",
    response_model=GorevYaniti,
    status_code=status.HTTP_201_CREATED,
    summary="Yeni görev oluştur",
)
def gorev_olustur(
    request: Request,
    istek: GorevOlusturIstegi,
    use_case: GorevOlusturUseCase = Depends(olustur_uc_getir),
) -> GorevYaniti:
    """Domain kurallarını doğrulayarak yeni bir görev oluşturur."""
    request.state.use_case = "GorevOlusturUseCase"
    cikti = use_case.calistir(
        GorevOlusturGirdi(
            baslik=istek.baslik,
            aciklama=istek.aciklama,
            oncelik=istek.oncelik,
            bitis_tarihi=istek.bitis_tarihi,
        )
    )
    yanit = GorevYaniti.dtodan_olustur(cikti)
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return yanit


@gorev_router.get(
    "",
    response_model=list[GorevYaniti],
    status_code=status.HTTP_200_OK,
    summary="Görevleri listele ve filtrele",
)
def gorevleri_listele(
    request: Request,
    durum: Optional[GorevDurumu] = Query(default=None, description="Duruma göre filtrele"),
    oncelik: Optional[GorevOnceligi] = Query(
        default=None, description="Önceliğe göre filtrele"
    ),
    arama: Optional[str] = Query(
        default=None, description="Başlık veya açıklamada metin ara"
    ),
    use_case: GorevListeleUseCase = Depends(listele_uc_getir),
) -> list[GorevYaniti]:
    """İsteğe bağlı durum, öncelik ve arama metnine göre görevleri listeler."""
    request.state.use_case = "GorevListeleUseCase"
    ciktilar = use_case.calistir(
        GorevFiltreGirdi(
            durum=durum,
            oncelik=oncelik,
            arama_metni=arama,
        )
    )
    yanit = [GorevYaniti.dtodan_olustur(cikti) for cikti in ciktilar]
    request.state.yanit_ozeti = {"listelenen_sayisi": len(yanit)}
    return yanit


@gorev_router.get(
    "/{gorev_id}",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Tekil görev detayını getir",
)
def gorev_getir(
    request: Request,
    gorev_id: str,
    use_case: GorevGetirUseCase = Depends(getir_uc_getir),
) -> GorevYaniti:
    """Verilen kimliğe sahip görevi döndürür."""
    request.state.use_case = "GorevGetirUseCase"
    cikti = use_case.calistir(gorev_id)
    yanit = GorevYaniti.dtodan_olustur(cikti)
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return yanit


@gorev_router.put(
    "/{gorev_id}",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Görev bilgilerini güncelle",
)
def gorev_guncelle(
    request: Request,
    gorev_id: str,
    istek: GorevGuncelleIstegi,
    use_case: GorevGuncelleUseCase = Depends(guncelle_uc_getir),
) -> GorevYaniti:
    """Mevcut görevin alanlarını kilit ve doğrulama kurallarına göre günceller."""
    request.state.use_case = "GorevGuncelleUseCase"
    cikti = use_case.calistir(
        GorevGuncelleGirdi(
            gorev_id=gorev_id,
            baslik=istek.baslik,
            aciklama=istek.aciklama,
            oncelik=istek.oncelik,
            bitis_tarihi=istek.bitis_tarihi,
            bitis_tarihini_temizle=istek.bitis_tarihini_temizle,
        )
    )
    yanit = GorevYaniti.dtodan_olustur(cikti)
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return yanit


@gorev_router.patch(
    "/{gorev_id}/durum",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Görev durumunu değiştir",
)
def gorev_durumu_degistir(
    request: Request,
    gorev_id: str,
    istek: GorevDurumDegistirIstegi,
    use_case: GorevDurumDegistirUseCase = Depends(durum_uc_getir),
) -> GorevYaniti:
    """Durum makinesi kurallarına göre görevi hedef duruma geçirir."""
    request.state.use_case = "GorevDurumDegistirUseCase"
    cikti = use_case.calistir(
        GorevDurumDegistirGirdi(
            gorev_id=gorev_id,
            yeni_durum=istek.yeni_durum,
        )
    )
    yanit = GorevYaniti.dtodan_olustur(cikti)
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return yanit


@gorev_router.delete(
    "/{gorev_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Görevi sil",
)
def gorev_sil(
    request: Request,
    gorev_id: str,
    use_case: GorevSilUseCase = Depends(sil_uc_getir),
) -> Response:
    """Kritik ve devam eden görev korumasını kontrol ederek görevi siler."""
    request.state.use_case = "GorevSilUseCase"
    use_case.calistir(gorev_id)
    request.state.yanit_ozeti = {"silinen_id": gorev_id, "durum": "silindi"}
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@sistem_router.get(
    "",
    response_model=SistemBilgisiYaniti,
    status_code=status.HTTP_200_OK,
    summary="Aktif sistem, repository ve telemetri bilgisini getir",
)
def sistem_bilgisi_getir(
    request: Request,
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> SistemBilgisiYaniti:
    """Aktif veri deposu adaptörünü, sınıf adını ve servis telemetri bilgisini döndürür."""
    ozet = _kayit_defterini_al(request).ozet()
    depo_tipi = konteyner.aktif_repo_tipi
    veritabani_yolu = (
        ":memory:" if depo_tipi == "memory" else konteyner.ayarlar.sqlite_db_path
    )
    return SistemBilgisiYaniti(
        uygulama="Clean Architecture Görev Yönetim Sistemi",
        surum="1.0.0",
        aktif_repository=depo_tipi,
        durum="calisiyor",
        depo_sinifi=konteyner.aktif_depo_sinifi,
        veritabani_yolu=veritabani_yolu,
        calisma_suresi_sn=float(ozet["calisma_suresi_sn"]),
        toplam_istek=int(ozet["toplam_istek"]),
        basarili_istek=int(ozet["basarili_istek"]),
        domain_ihlal_sayisi=int(ozet["domain_ihlal_sayisi"]),
        baslangic_zamani=str(ozet["baslangic_zamani"]),
    )


@sistem_router.post(
    "/depo-degistir",
    response_model=DepoDegistirYaniti,
    status_code=status.HTTP_200_OK,
    summary="Aktif repository adaptörünü çalışma zamanında değiştir (DIP)",
)
def repository_degistir(
    request: Request,
    istek: DepoDegistirIstegi,
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> Response:
    """Dependency Inversion prensibiyle Domain/Application koduna dokunmadan depoyu değiştirir."""
    request.state.use_case = "BagimlilikKonteyneri.depo_degistir"
    onceki = konteyner.aktif_repo_tipi
    try:
        yeni = konteyner.depo_degistir(istek.repo_tipi)
    except ValueError as hata:
        hata_yaniti = HataYaniti(
            hata_kodu="GECERSIZ_DEPO_TIPI",
            mesaj=str(hata),
            durum_kodu=status.HTTP_400_BAD_REQUEST,
        )
        request.state.yanit_ozeti = hata_yaniti.model_dump()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=hata_yaniti.model_dump(),
        )

    gorev_sayisi = len(konteyner.gorev_listele_use_case().calistir(GorevFiltreGirdi()))
    yanit = DepoDegistirYaniti(
        onceki_repository=onceki,
        aktif_repository=yeni,
        depo_sinifi=konteyner.aktif_depo_sinifi,
        gorev_sayisi=gorev_sayisi,
        mesaj=(
            f"Aktif adaptör '{onceki}' -> '{yeni}' ({konteyner.aktif_depo_sinifi}) "
            "olarak değiştirildi."
        ),
    )
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=yanit.model_dump(mode="json"),
    )


@sistem_router.get(
    "/loglar",
    response_model=LogListesiYaniti,
    status_code=status.HTTP_200_OK,
    summary="Gerçek zamanlı API ve Domain ihlal loglarını getir",
)
def sistem_loglarini_getir(
    request: Request,
    seviye: Optional[str] = Query(
        default=None, description="Filtreleme seviyesi (BASARILI, DOMAIN_IHLALI, HATA)"
    ),
    limit: int = Query(default=100, ge=1, le=250, description="Maksimum kayıt sayısı"),
) -> LogListesiYaniti:
    """Son API yürütme izlerini ve Domain kuralı ihlal kanıtlarını döndürür."""
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


@sistem_router.delete(
    "/loglar",
    response_model=LogTemizleYaniti,
    status_code=status.HTTP_200_OK,
    summary="İşlem log tamponunu temizle",
)
def sistem_loglarini_temizle(request: Request) -> LogTemizleYaniti:
    """Bellek içi işlem kayıt defterini temizler."""
    request.state.use_case = "IslemKayitDefteri.temizle"
    silinen = _kayit_defterini_al(request).temizle()
    yanit = LogTemizleYaniti(
        silinen=silinen,
        mesaj=f"{silinen} adet işlem kaydı temizlendi.",
    )
    request.state.yanit_ozeti = yanit.model_dump(mode="json")
    return yanit


@sistem_router.get(
    "/mimari-denetim",
    response_model=MimariDenetimYaniti,
    status_code=status.HTTP_200_OK,
    summary="Canlı AST bağımlılık kuralı denetimi çalıştır",
)
def mimari_denetim_calistir(request: Request) -> MimariDenetimYaniti:
    """Projedeki tüm Python dosyalarını AST ile tarayarak katman sınırlarını doğrular."""
    request.state.use_case = "AST.MimariDenetim"
    rapor: dict[str, Any] = ast_mimari_denetimi_calistir(PROJE_KOKU)
    request.state.yanit_ozeti = {
        "temiz": rapor["temiz"],
        "toplam_dosya": rapor["toplam_dosya"],
        "toplam_satir": rapor["toplam_satir"],
        "toplam_ihlal": rapor["toplam_ihlal"],
    }
    return MimariDenetimYaniti(**rapor)


@sistem_router.get(
    "/kaynak-kod",
    response_model=KaynakKodYaniti,
    status_code=status.HTTP_200_OK,
    summary="İzinli mimari katman dosyalarının kaynak kodunu salt okunur getir",
)
def kaynak_kod_getir(
    dosya: str = Query(..., description="Görevi dosya yolu (örn: domain/entities/gorev.py)"),
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


@sistem_router.post(
    "/ornek-veri-yukle",
    response_model=OrnekVeriYaniti,
    status_code=status.HTTP_201_CREATED,
    summary="Tüm yaşam döngüsü durumlarını ve iş kurallarını gösteren demo görevler yükle",
)
def ornek_veri_yukle(
    request: Request,
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> OrnekVeriYaniti:
    """Gerçek Use Case ve Domain kurallarından geçirerek 5 örnek görev oluşturur."""
    request.state.use_case = "GorevOlusturUseCase + GorevDurumDegistirUseCase"
    olustur_uc = konteyner.gorev_olustur_use_case()
    durum_uc = konteyner.gorev_durum_degistir_use_case()
    simdi = datetime.now(timezone.utc)

    senaryolar: list[dict[str, Any]] = [
        {
            "baslik": "API Sözleşmesi ve OpenAPI Doğrulaması",
            "aciklama": "BEKLEMEDE durumundaki görev doğrudan TAMAMLANDI yapılamaz (Kural 2).",
            "oncelik": GorevOnceligi.YUKSEK,
            "bitis": simdi + timedelta(days=5),
            "adimlar": [],
        },
        {
            "baslik": "Kritik Güvenlik ve Silme Koruma Deneyi",
            "aciklama": "KRITIK + DEVAM_EDIYOR görev doğrudan silinemez (Kural 4).",
            "oncelik": GorevOnceligi.KRITIK,
            "bitis": simdi + timedelta(days=2),
            "adimlar": [GorevDurumu.DEVAM_EDIYOR],
        },
        {
            "baslik": "AST Mimari Bağımlılık Denetim Raporu",
            "aciklama": "Domain ve Application katmanlarının sıfır dış bağımlılık kuralını izler.",
            "oncelik": GorevOnceligi.ORTA,
            "bitis": simdi + timedelta(days=4),
            "adimlar": [GorevDurumu.DEVAM_EDIYOR],
        },
        {
            "baslik": "Clean Architecture Çekirdek Katman Tasarımı",
            "aciklama": "TAMAMLANDI durumundaki görev salt okunur kilitlidir; düzenlenemez (Kural 3).",
            "oncelik": GorevOnceligi.YUKSEK,
            "bitis": simdi + timedelta(days=1),
            "adimlar": [GorevDurumu.DEVAM_EDIYOR, GorevDurumu.TAMAMLANDI],
        },
        {
            "baslik": "Eski Senkron Veritabanı Sürücüsünü Kaldır",
            "aciklama": "IPTAL_EDILDI terminal durumdur; yeniden başlatılamaz (Kural 2).",
            "oncelik": GorevOnceligi.DUSUK,
            "bitis": simdi + timedelta(days=3),
            "adimlar": [GorevDurumu.IPTAL_EDILDI],
        },
    ]

    olusanlar: list[GorevYaniti] = []
    for s in senaryolar:
        cikti = olustur_uc.calistir(
            GorevOlusturGirdi(
                baslik=s["baslik"],
                aciklama=s["aciklama"],
                oncelik=s["oncelik"],
                bitis_tarihi=s["bitis"],
            )
        )
        for hedef_durum in s["adimlar"]:
            cikti = durum_uc.calistir(
                GorevDurumDegistirGirdi(
                    gorev_id=cikti.id,
                    yeni_durum=hedef_durum,
                )
            )
        olusanlar.append(GorevYaniti.dtodan_olustur(cikti))

    yanit = OrnekVeriYaniti(
        eklenen_sayisi=len(olusanlar),
        aktif_repository=konteyner.aktif_repo_tipi,
        mesaj=(
            f"{len(olusanlar)} adet demo görev '{konteyner.aktif_repo_tipi}' "
            "deposuna gerçek Domain iş kurallarından geçirilerek eklendi."
        ),
        gorevler=olusanlar,
    )
    request.state.yanit_ozeti = {
        "eklenen_sayisi": len(olusanlar),
        "aktif_repository": konteyner.aktif_repo_tipi,
    }
    return yanit


def domain_hata_yoneticilerini_kaydet(uygulama: FastAPI) -> None:
    """Domain istisnalarını yapılandırılmış HTTP yanıtlarına çeviren Global Handler'ı kaydeder."""

    @uygulama.exception_handler(DomainHatasi)
    async def domain_hatasi_yakalayici(
        request: Request,
        hata: DomainHatasi,
    ) -> JSONResponse:
        durum_kodu = _DOMAIN_HTTP_ESLEMESI.get(
            type(hata), status.HTTP_400_BAD_REQUEST
        )
        icerik = HataYaniti(
            hata_kodu=hata.hata_kodu,
            mesaj=hata.mesaj,
            durum_kodu=durum_kodu,
        )
        icerik_dict = icerik.model_dump()
        request.state.domain_hata_kodu = hata.hata_kodu
        request.state.domain_hata_sinifi = type(hata).__name__
        request.state.domain_hata_mesaji = hata.mesaj
        request.state.domain_kaynak_dosya = _DOMAIN_KAYNAK_ESLEMESI.get(
            type(hata), "domain/exceptions/domain_hatalari.py"
        )
        request.state.yanit_ozeti = icerik_dict
        return JSONResponse(
            status_code=durum_kodu,
            content=icerik_dict,
        )
