"""HTTP veya veritabanından tamamen bağımsız Domain katmanı istisna sınıfları."""

from __future__ import annotations


class DomainHatasi(Exception):
    """Tüm Domain iş kuralı ihlalleri için temel istisna sınıfı."""

    hata_kodu: str = "DOMAIN_HATASI"

    def __init__(self, mesaj: str, hata_kodu: str | None = None) -> None:
        self.mesaj: str = mesaj
        if hata_kodu is not None:
            self.hata_kodu = hata_kodu
        super().__init__(mesaj)


class GecersizBaslikHatasi(DomainHatasi):
    """Görev başlığı boş veya izin verilen uzunluk sınırları dışındaysa fırlatılır."""

    hata_kodu: str = "GECERSIZ_BASLIK"

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj=mesaj, hata_kodu=self.hata_kodu)


class GecmisTarihHatasi(DomainHatasi):
    """Son teslim tarihi geçmiş bir tarih olarak belirlendiğinde fırlatılır."""

    hata_kodu: str = "GECMIS_TARIH"

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj=mesaj, hata_kodu=self.hata_kodu)


class GecersizDurumGecisiHatasi(DomainHatasi):
    """Durum makinesi kurallarına aykırı bir geçiş istendiğinde fırlatılır."""

    hata_kodu: str = "GECERSIZ_DURUM_GECISI"

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj=mesaj, hata_kodu=self.hata_kodu)


class KilitliGorevHatasi(DomainHatasi):
    """Tamamlanmış (salt okunur) bir görev güncellenmeye çalışıldığında fırlatılır."""

    hata_kodu: str = "KILITLI_GOREV"

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj=mesaj, hata_kodu=self.hata_kodu)


class KritikGorevSilinemezHatasi(DomainHatasi):
    """Kritik öncelikli ve devam eden bir görev doğrudan silinmek istendiğinde fırlatılır."""

    hata_kodu: str = "KRITIK_GOREV_SILINEMEZ"

    def __init__(self, mesaj: str) -> None:
        super().__init__(mesaj=mesaj, hata_kodu=self.hata_kodu)


class GorevBulunamadiHatasi(DomainHatasi):
    """İstenen kimliğe sahip görev bulunamadığında fırlatılır."""

    hata_kodu: str = "GOREV_BULUNAMADI"

    def __init__(self, gorev_id: str) -> None:
        self.gorev_id: str = gorev_id
        super().__init__(
            mesaj=f"'{gorev_id}' kimliğine sahip görev bulunamadı.",
            hata_kodu=self.hata_kodu,
        )
