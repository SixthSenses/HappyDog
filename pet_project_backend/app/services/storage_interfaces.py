"""Storage-related abstraction interfaces to reduce direct coupling to StorageService."""
from __future__ import annotations

from typing import Protocol


class StorageUrlProvider(Protocol):
    """Provides public and signed URL resolution without exposing storage internals."""

    def get_public_url(self, file_path: str) -> str:
        """Return a public URL for the given storage path."""

    def get_signed_url(self, file_path: str, expiration_hours: int = 1, method: str = "GET") -> str:
        """Return a signed URL granting temporary access to the path."""
