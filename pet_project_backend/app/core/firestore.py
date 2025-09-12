from __future__ import annotations

from typing import Optional, Any
import os

try:
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover
    firestore = None  # type: ignore

_DB_CLIENT: Optional[Any] = None


def is_docs_mode() -> bool:
    return os.environ.get("DOCS_MODE") == "1"


def initialize_firestore() -> Optional[Any]:
    """Initialize and cache a Firestore client unless in DOCS_MODE.

    Returns None in docs mode or when google.cloud is unavailable.
    Safe to call multiple times; subsequent calls return cached instance.
    """
    global _DB_CLIENT
    if _DB_CLIENT is not None:
        return _DB_CLIENT
    if is_docs_mode():
        _DB_CLIENT = None
        return _DB_CLIENT
    if firestore is None:  # library missing; degrade gracefully
        _DB_CLIENT = None
        return _DB_CLIENT
    try:  # pragma: no cover - environment dependent
        _DB_CLIENT = firestore.Client()
    except Exception:  # pragma: no cover
        _DB_CLIENT = None
    return _DB_CLIENT


def get_db() -> Optional[Any]:
    """Return previously initialized Firestore client (may be None)."""
    return _DB_CLIENT
