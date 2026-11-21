"""Presentation katmanı Pydantic istek ve yanıt şemaları."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

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
    """Çalışan uygulamanın aktif altyapı, repository ve telemetri durum bilgisi."""

    uygulama: str
    surum: str
    aktif_repository: str
    durum: str
    depo_sinifi: str = ""
    veritabani_yolu: str = ""
    calisma_suresi_sn: float = 0.0
    toplam_istek: int = 0
    basarili_istek: int = 0
    domain_ihlal_sayisi: int = 0
    baslangic_zamani: str = ""


class DepoDegistirIstegi(BaseModel):
    """Çalışma zamanında aktif repository adaptörünü değiştirme isteği."""

    repo_tipi: str = Field(
        ...,
        description="Hedef repository adaptörü ('sqlite' veya 'memory').",
        examples=["memory"],
    )


class DepoDegistirYaniti(BaseModel):
    """Repository değiştirme işlemi sonucunda döndürülen onay ve durum bilgisi."""

    onceki_repository: str
    aktif_repository: str
    depo_sinifi: str
    gorev_sayisi: int
    mesaj: str


class KatmanAdimiYaniti(BaseModel):
    """İsteğin geçtiği Clean Architecture katmanı ve yürütme durumu."""

    katman: str
    bilesen: str
    durum: str


class IslemLoguYaniti(BaseModel):
    """Sunucu tarafından kaydedilen gerçek zamanlı API ve Domain işlem izi."""

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
    katman_zinciri: list[KatmanAdimiYaniti]
    hata_kodu: Optional[str] = None
    hata_sinifi: Optional[str] = None
    kaynak_dosya: Optional[str] = None
    mesaj: str = ""
    istek_govdesi: Any = None
    yanit_ozeti: Any = None


class LogListesiYaniti(BaseModel):
    """Sistem işlem logları ve özet telemetri istatistikleri."""

    toplam_kayit: int
    ozet: dict[str, Any]
    kayitlar: list[IslemLoguYaniti]


class LogTemizleYaniti(BaseModel):
    """İşlem log tamponu temizleme sonucu."""

    silinen: int
    mesaj: str


class OrnekVeriYaniti(BaseModel):
    """Gerçek Use Case hattından geçirilen demo görev yükleme sonucu."""

    eklenen_sayisi: int
    aktif_repository: str
    mesaj: str
    gorevler: list[GorevYaniti]


class DosyaAstBilgisi(BaseModel):
    """Tek bir Python kaynak dosyasının canlı AST bağımlılık inceleme sonucu."""

    dosya: str
    katman: str
    satir_sayisi: int
    siniflar: list[str]
    fonksiyonlar: list[str]
    ic_importlar: list[str]
    stdlib_importlar: list[str]
    dis_importlar: list[str]
    ihlaller: list[str]
    temiz: bool


class KatmanAstOzeti(BaseModel):
    """Clean Architecture katmanı bazında AST uyumluluk özeti."""

    katman: str
    dosya_sayisi: int
    satir_sayisi: int
    ihlal_sayisi: int
    kural: str
    durum: str


class BagimlilikKenari(BaseModel):
    """Katmanlar arası tespit edilen gerçek import yönü ve sayısı."""

    kaynak: str
    hedef: str
    sayac: int


class MimariDenetimYaniti(BaseModel):
    """Tüm proje kaynak kodu için gerçek zamanlı AST bağımlılık denetim raporu."""

    temiz: bool
    toplam_dosya: int
    toplam_satir: int
    toplam_ihlal: int
    sure_ms: float
    katmanlar: list[KatmanAstOzeti]
    kenarlar: list[BagimlilikKenari]
    dosyalar: list[DosyaAstBilgisi]


class KaynakKodYaniti(BaseModel):
    """Seçilen Python kaynak dosyasının salt okunur içeriği."""

    dosya: str
    katman: str
    satir_sayisi: int
    icerik: str


class DurumGecisHucresiYaniti(BaseModel):
    """4x4 görev durum makinesi geçiş matrisindeki tek bir hücrenin tanımı."""

    kaynak: str
    hedef: str
    izinli: bool
    kural_aciklamasi: str


class MimariOzetYaniti(BaseModel):
    """Mimari kokpit sekmeleri için salt-okunur kapsam, durum matrisi, SOLID ve depo özeti."""

    aktif_repository: str
    depo_sinifi: str
    veritabani_yolu: str
    test_ozeti: dict[str, int]
    durum_matrisi: list[DurumGecisHucresiYaniti]
    is_kurallari: list[dict[str, Any]]
    solid_prensipleri: list[dict[str, Any]]
    katman_haritasi: list[dict[str, Any]]
    depo_karsilastirma: list[dict[str, Any]]
