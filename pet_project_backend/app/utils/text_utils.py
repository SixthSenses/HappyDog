"""Text utility helpers (introduced in PR2).

Currently provides a unified truncate function to be adopted gradually.
Duplicate legacy functions (e.g., _sanitize_summary) will be removed in PR4.
"""
from __future__ import annotations

from typing import Optional
from app.core.constants import SUMMARY_MAX_LEN

def truncate_summary(text: Optional[str], max_len: int = SUMMARY_MAX_LEN) -> str:
    """Return a sanitized, length-limited single-line summary.

    Steps:
    1. None -> empty string
    2. Strip leading/trailing whitespace
    3. Collapse internal newlines to spaces
    4. Truncate to max_len (safe for multibyte due to Python slicing on code points)
    """
    if not text:
        return ""
    sanitized = " ".join(text.strip().split())  # collapse all whitespace sequences
    if len(sanitized) <= max_len:
        return sanitized
    return sanitized[: max_len - 1] + "…"

__all__ = ["truncate_summary"]
