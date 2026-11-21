"""Görev öncelik seviyesi değer nesnesi."""

from __future__ import annotations

from enum import Enum


class GorevOnceligi(str, Enum):
    """Görevlerin aciliyet ve iş etkisine göre öncelik düzeyleri."""

    DUSUK = "DUSUK"
    ORTA = "ORTA"
    YUKSEK = "YUKSEK"
    KRITIK = "KRITIK"
