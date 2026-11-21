"""FastAPI uygulama giriş noktası, Composition Root ve telemetri ara katmanı."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, AsyncIterator, Awaitable, Callable, Optional
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri
from infrastructure.observability.telemetri import IslemKayitDefteri, IslemKaydi
from presentation.api.gorev_router import (
    domain_hata_yoneticilerini_kaydet,
    gorev_router,
    sistem_router,
)
from presentation.api.mimari_router import mimari_router

WEB_DIZINI: Path = Path(__file__).resolve().parent / "presentation" / "web"
INDEX_DOSYASI: Path = WEB_DIZINI / "index.html"

_PASIF_LOG_DISI_YOLLAR: frozenset[str] = frozenset(
    {
        "/api/v1/sistem",
        "/api/v1/sistem/loglar",
        "/api/v1/sistem/kaynak-kod",
        "/api/v1/mimari/ozet",
        "/api/v1/mimari/izler",
        "/api/v1/mimari/kaynak-kod",
    }
)


def _katman_zinciri_olustur(
    metot: str,
    yol: str,
    durum_kodu: int,
    use_case: str,
    aktif_repo: str,
    depo_sinifi: str,
    domain_hata_kodu: Optional[str],
    domain_hata_sinifi: Optional[str],
) -> list[dict[str, str]]:
    """İsteğin geçtiği gerçek Clean Architecture katman izini oluşturur."""
    if domain_hata_kodu:
        if domain_hata_kodu == "GOREV_BULUNAMADI":
            return [
                {"katman": "Presentation", "bilesen": f"FastAPI Router ({metot} {yol})", "durum": "OK"},
                {"katman": "Application", "bilesen": use_case, "durum": "OK"},
                {"katman": "Infrastructure", "bilesen": f"{depo_sinifi} (Kayıt Yok)", "durum": "OK"},
                {"katman": "Domain", "bilesen": f"{domain_hata_sinifi} [{domain_hata_kodu}]", "durum": "IHLAL"},
            ]
        return [
            {"katman": "Presentation", "bilesen": f"FastAPI Router ({metot} {yol})", "durum": "OK"},
            {"katman": "Application", "bilesen": use_case, "durum": "OK"},
            {"katman": "Domain", "bilesen": f"{domain_hata_sinifi} [{domain_hata_kodu}]", "durum": "IHLAL"},
            {"katman": "Infrastructure", "bilesen": f"{depo_sinifi} (Yazım Engellendi)", "durum": "ATLANDI"},
        ]

    if durum_kodu == 422:
        return [
            {"katman": "Presentation", "bilesen": "Pydantic Şema Doğrulaması", "durum": "IHLAL"},
            {"katman": "Application", "bilesen": f"{use_case} (Çağrılmadı)", "durum": "ATLANDI"},
            {"katman": "Domain", "bilesen": "Domain Kuralları (Çağrılmadı)", "durum": "ATLANDI"},
            {"katman": "Infrastructure", "bilesen": f"{depo_sinifi} (Çağrılmadı)", "durum": "ATLANDI"},
        ]

    if yol in {
        "/api/v1/sistem/mimari-denetim",
        "/api/v1/mimari/ast-denetim",
        "/api/v1/sistem/depo-degistir",
    } or (yol == "/api/v1/sistem/loglar" and metot == "DELETE"):
        return [
            {"katman": "Presentation", "bilesen": f"FastAPI Router ({metot} {yol})", "durum": "OK"},
            {"katman": "Infrastructure", "bilesen": use_case, "durum": "OK"},
        ]

    return [
        {"katman": "Presentation", "bilesen": f"FastAPI Router ({metot} {yol})", "durum": "OK"},
        {"katman": "Application", "bilesen": use_case, "durum": "OK"},
        {"katman": "Domain", "bilesen": "Gorev Entity & Değer Nesneleri", "durum": "OK"},
        {"katman": "Infrastructure", "bilesen": f"{depo_sinifi} ({aktif_repo})", "durum": "OK"},
    ]


def uygulama_olustur(
    ayarlar: Optional[Ayarlar] = None,
    konteyner: Optional[BagimlilikKonteyneri] = None,
) -> FastAPI:
    """Clean Architecture katmanlarını bağlayarak FastAPI uygulamasını yapılandırır."""

    @asynccontextmanager
    async def yasam_dongusu(app: FastAPI) -> AsyncIterator[None]:
        disaridan_verildi = app.state.konteyner is not None
        if app.state.konteyner is None:
            app.state.konteyner = BagimlilikKonteyneri(ayarlar=app.state.ayarlar)
        try:
            yield
        finally:
            if app.state.konteyner is not None:
                app.state.konteyner.kapat()
                if not disaridan_verildi:
                    app.state.konteyner = None

    app = FastAPI(
        title="Clean Architecture Görev Yönetim Sistemi",
        description=(
            "Saf Clean Architecture, SOLID prensipleri ve çift kalıcılık "
            "(SQLite / In-Memory) desteği ile geliştirilmiş kurumsal görev yönetim API'si."
        ),
        version="1.0.0",
        lifespan=yasam_dongusu,
    )
    app.state.ayarlar = ayarlar
    app.state.konteyner = konteyner
    app.state.kayit_defteri = IslemKayitDefteri()

    @app.middleware("http")
    async def islem_telemetri_ara_katmani(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        yol = request.url.path
        if not yol.startswith("/api/v1/"):
            response = await call_next(request)
            if yol == "/" or yol.startswith("/static/"):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            return response

        iz_id = f"TR-{uuid4().hex[:8].upper()}"
        baslangic = time.perf_counter()

        istek_govdesi: Any = None
        if request.method in {"POST", "PUT", "PATCH"}:
            ham_govde = await request.body()
            if ham_govde:
                try:
                    istek_govdesi = json.loads(ham_govde.decode("utf-8"))
                except Exception:
                    istek_govdesi = ham_govde.decode("utf-8", errors="replace")[:400]

        response = await call_next(request)
        sure_ms = round((time.perf_counter() - baslangic) * 1000, 2)

        aktif_konteyner: Optional[BagimlilikKonteyneri] = getattr(
            request.app.state, "konteyner", None
        )
        aktif_repo = (
            aktif_konteyner.aktif_repo_tipi if aktif_konteyner is not None else "sqlite"
        )
        depo_sinifi = (
            aktif_konteyner.aktif_depo_sinifi
            if aktif_konteyner is not None
            else "BagimlilikKonteyneri"
        )

        use_case = getattr(request.state, "use_case", f"{request.method} {yol}")
        domain_hata_kodu = getattr(request.state, "domain_hata_kodu", None)
        domain_hata_sinifi = getattr(request.state, "domain_hata_sinifi", None)
        domain_hata_mesaji = getattr(request.state, "domain_hata_mesaji", None)
        kaynak_dosya = getattr(request.state, "domain_kaynak_dosya", None)
        yanit_ozeti = getattr(request.state, "yanit_ozeti", None)

        response.headers["X-Trace-Id"] = iz_id
        response.headers["X-Process-Time-Ms"] = f"{sure_ms:.2f}"
        response.headers["X-Active-Repository"] = aktif_repo
        response.headers["X-Active-Repo-Class"] = depo_sinifi
        response.headers["X-Executed-UseCase"] = use_case
        if domain_hata_sinifi:
            response.headers["X-Domain-Exception"] = domain_hata_sinifi
        if domain_hata_kodu:
            response.headers["X-Domain-Error-Code"] = domain_hata_kodu

        if not (request.method == "GET" and yol in _PASIF_LOG_DISI_YOLLAR):
            if domain_hata_kodu:
                seviye = "DOMAIN_IHLALI"
                mesaj = domain_hata_mesaji or domain_hata_kodu
            elif response.status_code >= 400:
                seviye = "HATA"
                mesaj = f"HTTP {response.status_code} istemci/doğrulama hatası"
            else:
                seviye = "BASARILI"
                mesaj = f"{use_case} başarıyla tamamlandı ({aktif_repo})"

            zincir = _katman_zinciri_olustur(
                metot=request.method,
                yol=yol,
                durum_kodu=response.status_code,
                use_case=use_case,
                aktif_repo=aktif_repo,
                depo_sinifi=depo_sinifi,
                domain_hata_kodu=domain_hata_kodu,
                domain_hata_sinifi=domain_hata_sinifi,
            )

            kayit = IslemKaydi(
                iz_id=iz_id,
                zaman=datetime.now(timezone.utc).isoformat(),
                metot=request.method,
                yol=yol if not request.url.query else f"{yol}?{request.url.query}",
                durum_kodu=response.status_code,
                sure_ms=sure_ms,
                seviye=seviye,
                aktif_repository=aktif_repo,
                depo_sinifi=depo_sinifi,
                use_case=use_case,
                katman_zinciri=zincir,
                hata_kodu=domain_hata_kodu,
                hata_sinifi=domain_hata_sinifi,
                kaynak_dosya=kaynak_dosya,
                mesaj=mesaj,
                istek_govdesi=istek_govdesi,
                yanit_ozeti=yanit_ozeti,
            )
            defter: Optional[IslemKayitDefteri] = getattr(
                request.app.state, "kayit_defteri", None
            )
            if defter is None:
                defter = IslemKayitDefteri()
                request.app.state.kayit_defteri = defter
            defter.kayit_ekle(kayit)

        return response

    domain_hata_yoneticilerini_kaydet(app)
    app.include_router(gorev_router)
    app.include_router(sistem_router)
    app.include_router(mimari_router)

    if WEB_DIZINI.is_dir():
        app.mount("/static", StaticFiles(directory=WEB_DIZINI), name="static")

    @app.get("/", include_in_schema=False)
    def web_paneli() -> FileResponse:
        """Görev Yönetim Web Panelini (SPA) sunar."""
        return FileResponse(INDEX_DOSYASI)

    return app


uygulama: FastAPI = uygulama_olustur()
