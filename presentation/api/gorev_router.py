"""FastAPI RESTful uç noktaları ve Global Domain Exception Handler."""

from __future__ import annotations

from typing import Optional

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
from presentation.api.semalar import (
    GorevDurumDegistirIstegi,
    GorevGuncelleIstegi,
    GorevOlusturIstegi,
    GorevYaniti,
    HataYaniti,
    SistemBilgisiYaniti,
)

_DOMAIN_HTTP_ESLEMESI: dict[type[DomainHatasi], int] = {
    GorevBulunamadiHatasi: status.HTTP_404_NOT_FOUND,
    GecersizBaslikHatasi: status.HTTP_422_UNPROCESSABLE_CONTENT,
    GecmisTarihHatasi: status.HTTP_422_UNPROCESSABLE_CONTENT,
    GecersizDurumGecisiHatasi: status.HTTP_400_BAD_REQUEST,
    KilitliGorevHatasi: status.HTTP_400_BAD_REQUEST,
    KritikGorevSilinemezHatasi: status.HTTP_400_BAD_REQUEST,
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
    istek: GorevOlusturIstegi,
    use_case: GorevOlusturUseCase = Depends(olustur_uc_getir),
) -> GorevYaniti:
    """Domain kurallarını doğrulayarak yeni bir görev oluşturur."""
    cikti = use_case.calistir(
        GorevOlusturGirdi(
            baslik=istek.baslik,
            aciklama=istek.aciklama,
            oncelik=istek.oncelik,
            bitis_tarihi=istek.bitis_tarihi,
        )
    )
    return GorevYaniti.dtodan_olustur(cikti)


@gorev_router.get(
    "",
    response_model=list[GorevYaniti],
    status_code=status.HTTP_200_OK,
    summary="Görevleri listele ve filtrele",
)
def gorevleri_listele(
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
    ciktilar = use_case.calistir(
        GorevFiltreGirdi(
            durum=durum,
            oncelik=oncelik,
            arama_metni=arama,
        )
    )
    return [GorevYaniti.dtodan_olustur(cikti) for cikti in ciktilar]


@gorev_router.get(
    "/{gorev_id}",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Tekil görev detayını getir",
)
def gorev_getir(
    gorev_id: str,
    use_case: GorevGetirUseCase = Depends(getir_uc_getir),
) -> GorevYaniti:
    """Verilen kimliğe sahip görevi döndürür."""
    cikti = use_case.calistir(gorev_id)
    return GorevYaniti.dtodan_olustur(cikti)


@gorev_router.put(
    "/{gorev_id}",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Görev bilgilerini güncelle",
)
def gorev_guncelle(
    gorev_id: str,
    istek: GorevGuncelleIstegi,
    use_case: GorevGuncelleUseCase = Depends(guncelle_uc_getir),
) -> GorevYaniti:
    """Mevcut görevin alanlarını kilit ve doğrulama kurallarına göre günceller."""
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
    return GorevYaniti.dtodan_olustur(cikti)


@gorev_router.patch(
    "/{gorev_id}/durum",
    response_model=GorevYaniti,
    status_code=status.HTTP_200_OK,
    summary="Görev durumunu değiştir",
)
def gorev_durumu_degistir(
    gorev_id: str,
    istek: GorevDurumDegistirIstegi,
    use_case: GorevDurumDegistirUseCase = Depends(durum_uc_getir),
) -> GorevYaniti:
    """Durum makinesi kurallarına göre görevi hedef duruma geçirir."""
    cikti = use_case.calistir(
        GorevDurumDegistirGirdi(
            gorev_id=gorev_id,
            yeni_durum=istek.yeni_durum,
        )
    )
    return GorevYaniti.dtodan_olustur(cikti)


@gorev_router.delete(
    "/{gorev_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Görevi sil",
)
def gorev_sil(
    gorev_id: str,
    use_case: GorevSilUseCase = Depends(sil_uc_getir),
) -> Response:
    """Kritik ve devam eden görev korumasını kontrol ederek görevi siler."""
    use_case.calistir(gorev_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@sistem_router.get(
    "",
    response_model=SistemBilgisiYaniti,
    status_code=status.HTTP_200_OK,
    summary="Aktif sistem ve repository bilgisini getir",
)
def sistem_bilgisi_getir(
    konteyner: BagimlilikKonteyneri = Depends(_konteyneri_al),
) -> SistemBilgisiYaniti:
    """Aktif veri deposu adaptörünü ve servis sağlık bilgisini döndürür."""
    return SistemBilgisiYaniti(
        uygulama="Clean Architecture Görev Yönetim Sistemi",
        surum="1.0.0",
        aktif_repository=konteyner.aktif_repo_tipi,
        durum="calisiyor",
    )


def domain_hata_yoneticilerini_kaydet(uygulama: FastAPI) -> None:
    """Domain istisnalarını yapılandırılmış HTTP yanıtlarına çeviren Global Handler'ı kaydeder."""

    @uygulama.exception_handler(DomainHatasi)
    async def domain_hatasi_yakalayici(
        _request: Request,
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
        return JSONResponse(
            status_code=durum_kodu,
            content=icerik.model_dump(),
        )
