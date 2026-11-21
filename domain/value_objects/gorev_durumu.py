"""Görev durumu değer nesnesi ve durum makinesi geçiş kuralları."""

from __future__ import annotations

from enum import Enum


class GorevDurumu(str, Enum):
    """Görevin yaşam döngüsü boyunca bulunabileceği geçerli durumlar."""

    BEKLEMEDE = "BEKLEMEDE"
    DEVAM_EDIYOR = "DEVAM_EDIYOR"
    TAMAMLANDI = "TAMAMLANDI"
    IPTAL_EDILDI = "IPTAL_EDILDI"

    def izinli_gecisler(self) -> frozenset[GorevDurumu]:
        """Bu durumdan geçiş yapılabilecek hedef durumları döndürür."""
        return _IZINLI_GECISLER[self]

    def gecis_yapilabilir_mi(self, hedef_durum: GorevDurumu) -> bool:
        """Verilen hedef duruma geçişin durum makinesine uygun olup olmadığını kontrol eder."""
        return hedef_durum in _IZINLI_GECISLER[self]


_IZINLI_GECISLER: dict[GorevDurumu, frozenset[GorevDurumu]] = {
    GorevDurumu.BEKLEMEDE: frozenset(
        {GorevDurumu.DEVAM_EDIYOR, GorevDurumu.IPTAL_EDILDI}
    ),
    GorevDurumu.DEVAM_EDIYOR: frozenset(
        {
            GorevDurumu.TAMAMLANDI,
            GorevDurumu.BEKLEMEDE,
            GorevDurumu.IPTAL_EDILDI,
        }
    ),
    GorevDurumu.TAMAMLANDI: frozenset(),
    GorevDurumu.IPTAL_EDILDI: frozenset(),
}
