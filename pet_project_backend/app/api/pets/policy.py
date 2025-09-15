"""Access policy objects for the Pets domain (PR2).

Encapsulates authorization rules to keep route handlers thin.
"""
from __future__ import annotations

from typing import Optional


class PetAccessPolicy:
    """Authorization logic for pet profile view access."""

    ALLOWED_VIEWS = {"mypage", "petcare", "social"}

    def validate_view(self, view: str):
        if view not in self.ALLOWED_VIEWS:
            raise ValueError("INVALID_VIEW")

    def ensure_view_permission(
        self, current_user_id: Optional[str], target_user_id: Optional[str], view: str
    ) -> None:
        """Raise appropriate errors if access is not permitted.

        Rules:
          - Viewing another user's profile requires authentication.
          - mypage/petcare are owner-only.
          - social is public (requires auth if targeting other user? kept auth if anonymous for own profile only).
        """
        self.validate_view(view)

        if target_user_id != current_user_id:
            # Accessing someone else's pet profile
            if not current_user_id:
                raise PermissionError("AUTHENTICATION_REQUIRED")
            if view in ("mypage", "petcare"):
                raise PermissionError("PERMISSION_DENIED")

__all__ = ["PetAccessPolicy"]
