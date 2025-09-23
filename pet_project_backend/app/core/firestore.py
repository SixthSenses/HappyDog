from __future__ import annotations

from typing import Optional, Any
import os
import logging

try:  # Preferred client (uses Application Default Credentials)
    from google.cloud import firestore  # type: ignore
except Exception:  # pragma: no cover
    firestore = None  # type: ignore

try:  # Fallback via firebase_admin (if already initialized with explicit credentials)
    import firebase_admin  # type: ignore
    from firebase_admin import firestore as admin_firestore  # type: ignore
except Exception:  # pragma: no cover
    firebase_admin = None  # type: ignore
    admin_firestore = None  # type: ignore

_DB_CLIENT: Optional[Any] = None


def is_docs_mode() -> bool:
    return os.environ.get("DOCS_MODE") == "1"


def initialize_firestore() -> Optional[Any]:
    """Initialize and cache a Firestore client unless in DOCS_MODE.

        Resolution order:
            1. firebase_admin already initialized -> firebase_admin.firestore.client() (explicit service account from .env)
            2. google.cloud.firestore.Client() (ADC)

    Returns None when:
      - DOCS_MODE enabled
      - Both clients unavailable / initialization failed

    Adds verbose logging so that silent failures are easier to diagnose.
    Safe to call multiple times; subsequent calls return cached instance.
    """
    global _DB_CLIENT
    if _DB_CLIENT is not None:
        return _DB_CLIENT

    if is_docs_mode():
        logging.info("Firestore initialization skipped (DOCS_MODE=1)")
        _DB_CLIENT = None
        return _DB_CLIENT

    # 1) Prefer firebase_admin if already initialized with explicit credentials
    if firebase_admin is not None and getattr(firebase_admin, '_apps', None):
        try:  # pragma: no cover
            _DB_CLIENT = admin_firestore.client()
            logging.info("Firestore client initialized via firebase_admin (preferred)")
            return _DB_CLIENT
        except Exception as e:  # pragma: no cover
            logging.error(f"firebase_admin Firestore init failed: {e}")

    # 2) Fallback to google.cloud (ADC)
    if firestore is not None:
        try:  # pragma: no cover - environment dependent
            _DB_CLIENT = firestore.Client()
            logging.info("Firestore client initialized via google.cloud.firestore (ADC)")
            return _DB_CLIENT
        except Exception as e:  # pragma: no cover
            logging.warning(f"ADC Firestore client init failed (google.cloud): {e}")
    else:
        logging.warning("google.cloud.firestore unavailable; ADC path not usable")

    logging.warning("Firestore client not initialized (all strategies failed)")
    _DB_CLIENT = None
    return _DB_CLIENT


def get_db() -> Optional[Any]:
    """Return previously initialized Firestore client (may be None)."""
    return _DB_CLIENT
