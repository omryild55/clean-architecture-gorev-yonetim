"""Domain depo sözleşmesini uygulayan SQLAlchemy + SQLite adaptörü."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import DateTime, String, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from domain.entities.gorev import Gorev
from domain.exceptions.domain_hatalari import GorevBulunamadiHatasi
from domain.repositories.gorev_repository_arayuzu import GorevRepositoryArayuzu
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi
from domain.value_objects.tarih_dogrulama import tarihi_utc_normalize_et


class Taban(DeclarativeBase):
    """SQLAlchemy ORM modelleri için temel deklaratif sınıf."""


class GorevTablosu(Taban):
    """Görev varlığının SQLite veritabanı tablo eşlemesi."""

    __tablename__ = "gorevler"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    baslik: Mapped[str] = mapped_column(String(100), nullable=False)
    aciklama: Mapped[str] = mapped_column(Text, nullable=False, default="")
    durum: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    oncelik: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    bitis_tarihi: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    olusturulma_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    guncellenme_tarihi: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class SqliteGorevRepository(GorevRepositoryArayuzu):
    """SQLAlchemy ORM kullanarak SQLite veritabanında görevleri saklayan adaptör."""

    def __init__(self, veritabani_url: str = "sqlite:///gorevler.db") -> None:
        self._veritabani_url: str = veritabani_url
        self._ust_dizini_hazirla(veritabani_url)

        motor_parametreleri: dict[str, object] = {
            "connect_args": {"check_same_thread": False},
        }
        if veritabani_url == "sqlite:///:memory:":
            motor_parametreleri["poolclass"] = StaticPool

        self._motor: Engine = create_engine(veritabani_url, **motor_parametreleri)
        self._oturum_fabrikasi: sessionmaker[Session] = sessionmaker(
            bind=self._motor,
            expire_on_commit=False,
        )
        Taban.metadata.create_all(self._motor)

    @staticmethod
    def _ust_dizini_hazirla(veritabani_url: str) -> None:
        """Dosya tabanlı SQLite URL'leri için hedef üst dizini oluşturur."""
        if not veritabani_url.startswith("sqlite:///") or ":memory:" in veritabani_url:
            return
        dosya_yolu = veritabani_url.removeprefix("sqlite:///")
        if dosya_yolu:
            Path(dosya_yolu).parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _kayittan_varliga(kayit: GorevTablosu) -> Gorev:
        """ORM satırını saf Domain Gorev varlığına dönüştürür."""
        return Gorev.yeniden_olustur(
            gorev_id=kayit.id,
            baslik=kayit.baslik,
            aciklama=kayit.aciklama,
            durum=GorevDurumu(kayit.durum),
            oncelik=GorevOnceligi(kayit.oncelik),
            bitis_tarihi=kayit.bitis_tarihi,
            olusturulma_tarihi=kayit.olusturulma_tarihi,
            guncellenme_tarihi=kayit.guncellenme_tarihi,
        )

    @staticmethod
    def _varliktan_kayda(gorev: Gorev) -> GorevTablosu:
        """Domain Gorev varlığından yeni bir ORM satırı üretir."""
        return GorevTablosu(
            id=gorev.id,
            baslik=gorev.baslik,
            aciklama=gorev.aciklama,
            durum=gorev.durum.value,
            oncelik=gorev.oncelik.value,
            bitis_tarihi=(
                tarihi_utc_normalize_et(gorev.bitis_tarihi)
                if gorev.bitis_tarihi is not None
                else None
            ),
            olusturulma_tarihi=tarihi_utc_normalize_et(gorev.olusturulma_tarihi),
            guncellenme_tarihi=tarihi_utc_normalize_et(gorev.guncellenme_tarihi),
        )

    def kaydet(self, gorev: Gorev) -> Gorev:
        """Yeni görevi SQLite veritabanına ekler."""
        kayit = self._varliktan_kayda(gorev)
        with self._oturum_fabrikasi() as oturum:
            oturum.add(kayit)
            oturum.commit()
            oturum.refresh(kayit)
            return self._kayittan_varliga(kayit)

    def id_ile_getir(self, gorev_id: str) -> Optional[Gorev]:
        """Kimliğe göre görevi SQLite veritabanından getirir."""
        with self._oturum_fabrikasi() as oturum:
            kayit = oturum.get(GorevTablosu, gorev_id)
            return self._kayittan_varliga(kayit) if kayit is not None else None

    def tumunu_listele(
        self,
        durum: Optional[GorevDurumu] = None,
        oncelik: Optional[GorevOnceligi] = None,
        arama_metni: Optional[str] = None,
    ) -> list[Gorev]:
        """Ölçütlere uyan görevleri oluşturulma tarihine göre azalan sırada getirir."""
        sorgu = select(GorevTablosu)

        if durum is not None:
            sorgu = sorgu.where(GorevTablosu.durum == durum.value)

        if oncelik is not None:
            sorgu = sorgu.where(GorevTablosu.oncelik == oncelik.value)

        sorgu = sorgu.order_by(GorevTablosu.olusturulma_tarihi.desc())

        with self._oturum_fabrikasi() as oturum:
            kayitlar = oturum.scalars(sorgu).all()

        varliklar = [self._kayittan_varliga(kayit) for kayit in kayitlar]

        if arama_metni is not None and arama_metni.strip():
            aranan = arama_metni.strip().casefold()
            varliklar = [
                g
                for g in varliklar
                if aranan in g.baslik.casefold() or aranan in g.aciklama.casefold()
            ]

        return varliklar

    def guncelle(self, gorev: Gorev) -> Gorev:
        """Mevcut görevin güncel alanlarını SQLite veritabanına işler."""
        with self._oturum_fabrikasi() as oturum:
            kayit = oturum.get(GorevTablosu, gorev.id)
            if kayit is None:
                raise GorevBulunamadiHatasi(gorev.id)

            kayit.baslik = gorev.baslik
            kayit.aciklama = gorev.aciklama
            kayit.durum = gorev.durum.value
            kayit.oncelik = gorev.oncelik.value
            kayit.bitis_tarihi = (
                tarihi_utc_normalize_et(gorev.bitis_tarihi)
                if gorev.bitis_tarihi is not None
                else None
            )
            kayit.guncellenme_tarihi = tarihi_utc_normalize_et(gorev.guncellenme_tarihi)

            oturum.commit()
            oturum.refresh(kayit)
            return self._kayittan_varliga(kayit)

    def sil(self, gorev_id: str) -> bool:
        """Kimliğe göre görevi SQLite veritabanından kalıcı olarak siler."""
        with self._oturum_fabrikasi() as oturum:
            kayit = oturum.get(GorevTablosu, gorev_id)
            if kayit is None:
                return False
            oturum.delete(kayit)
            oturum.commit()
            return True

    def kapat(self) -> None:
        """Veritabanı bağlantı havuzunu kapatır ve dosya kilitlerini serbest bırakır."""
        self._motor.dispose()
