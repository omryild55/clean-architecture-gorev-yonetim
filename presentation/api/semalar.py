"""Presentation katmanı Pydantic istek ve yanıt şemaları."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from application.dtos.gorev_dto import GorevCikti
from domain.value_objects.gorev_durumu import GorevDurumu
from domain.value_objects.gorev_onceligi import GorevOnceligi


class GorevOlusturIstegi(BaseModel):
    """Yeni görev oluşturma API istek gövdesi."""

    baslik: str = Field(
        ...,
        description="Görev başlığı (3-100 karakter arası, Domain katmanında doğrulanır).",
        examples=["Mimari Diyagramları Güncelle"],
    )
    aciklama: str = Field(
        default="",
        description="Görevin kapsamı ve teknik detayları.",
        examples=["Clean Architecture bağımlılık diyagramını C4 formatında çiz."],
    )
    oncelik: GorevOnceligi = Field(
        default=GorevOnceligi.ORTA,
        description="Görev öncelik düzeyi.",
    )
    bitis_tarihi: Optional[datetime] = Field(
        default=None,
        description="Son teslim tarihi (ISO-8601 formatında, geçmiş tarih olamaz).",
    )


class GorevGuncelleIstegi(BaseModel):
    """Mevcut görevi güncelleme API istek gövdesi."""

    baslik: Optional[str] = Field(
        default=None,
        description="Yeni görev başlığı (3-100 karakter arası).",
    )
    aciklama: Optional[str] = Field(
        default=None,
        description="Yeni görev açıklaması.",
    )
    oncelik: Optional[GorevOnceligi] = Field(
        default=None,
        description="Yeni öncelik seviyesi.",
    )
    bitis_tarihi: Optional[datetime] = Field(
        default=None,
        description="Yeni son teslim tarihi (geçmiş tarih olamaz).",
    )
    bitis_tarihini_temizle: bool = Field(
        default=False,
        description="True gönderilirse ve bitis_tarihi boşsa mevcut son teslim tarihi kaldırılır.",
    )


class GorevDurumDegistirIstegi(BaseModel):
    """Görev durumu geçişi için API istek gövdesi."""

    yeni_durum: GorevDurumu = Field(
        ...,
        description="Durum makinesi kurallarına uygun hedef durum.",
    )


class GorevYaniti(BaseModel):
    """API tarafından döndürülen görev yanıt şeması."""

    id: str
    baslik: str
    aciklama: str
    durum: GorevDurumu
    oncelik: GorevOnceligi
    bitis_tarihi: Optional[datetime]
    olusturulma_tarihi: datetime
    guncellenme_tarihi: datetime
    izinli_gecisler: list[GorevDurumu]

    @classmethod
    def dtodan_olustur(cls, dto: GorevCikti) -> GorevYaniti:
        """Application katmanı çıktı DTO'sunu HTTP yanıt şemasına dönüştürür."""
        return cls(
            id=dto.id,
            baslik=dto.baslik,
            aciklama=dto.aciklama,
            durum=dto.durum,
            oncelik=dto.oncelik,
            bitis_tarihi=dto.bitis_tarihi,
            olusturulma_tarihi=dto.olusturulma_tarihi,
            guncellenme_tarihi=dto.guncellenme_tarihi,
            izinli_gecisler=list(dto.izinli_gecisler),
        )


class HataYaniti(BaseModel):
    """Domain ve iş kuralı ihlalleri için standart hata yanıt modeli."""

    hata_kodu: str
    mesaj: str
    durum_kodu: int


class SistemBilgisiYaniti(BaseModel):
    """Çalışan uygulamanın aktif altyapı ve repository durum bilgisi."""

    uygulama: str
    surum: str
    aktif_repository: str
    durum: str
