"""FastAPI uygulama giriş noktası ve Composition Root."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse

from infrastructure.config.ayarlar import Ayarlar, BagimlilikKonteyneri
from presentation.api.gorev_router import (
    domain_hata_yoneticilerini_kaydet,
    gorev_router,
    sistem_router,
)

WEB_DIZINI: Path = Path(__file__).resolve().parent / "presentation" / "web"
INDEX_DOSYASI: Path = WEB_DIZINI / "index.html"


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

    domain_hata_yoneticilerini_kaydet(app)
    app.include_router(gorev_router)
    app.include_router(sistem_router)

    @app.get("/", include_in_schema=False)
    def web_paneli() -> FileResponse:
        """Görev Yönetim Web Panelini (SPA) sunar."""
        return FileResponse(INDEX_DOSYASI)

    return app


uygulama: FastAPI = uygulama_olustur()
