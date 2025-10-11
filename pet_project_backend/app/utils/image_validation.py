"""Lightweight image validation helpers for biometric uploads (PR2B).

We avoid heavy dependencies (e.g., Pillow) for first-pass validation – simple
magic-byte prefix checks and minimal sanity guards.
"""
from __future__ import annotations

from typing import Tuple, Optional

from app.core.constants import ALLOWED_IMAGE_MAGICS

MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB provisional limit


class ImageValidationResult:
    __slots__ = ("ok", "format", "error")

    def __init__(self, ok: bool, format: Optional[str] = None, error: Optional[str] = None):
        self.ok = ok
        self.format = format
        self.error = error

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"ImageValidationResult(ok={self.ok}, format={self.format}, error={self.error})"


def detect_image_format(data: bytes) -> Optional[str]:
    for magic, name in ALLOWED_IMAGE_MAGICS.items():
        if data.startswith(magic):
            if name == "RIFF":  # Heuristic WEBP check
                if b"WEBP" in data[8:16]:
                    return "WEBP"
                return None
            return name
    return None


def validate_image_bytes(data: bytes) -> ImageValidationResult:
    if not data:
        return ImageValidationResult(False, error="empty")
    if len(data) > MAX_IMAGE_SIZE_BYTES:
        return ImageValidationResult(False, error="too_large")
    fmt = detect_image_format(data[:32])  # first 32 bytes enough for our magics
    if not fmt:
        return ImageValidationResult(False, error="unsupported")
    return ImageValidationResult(True, format=fmt)


__all__ = [
    "validate_image_bytes",
    "detect_image_format",
    "ImageValidationResult",
    "MAX_IMAGE_SIZE_BYTES",
]