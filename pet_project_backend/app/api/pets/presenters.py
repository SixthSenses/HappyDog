"""Pets domain presenters.

Responsible for shaping API response payloads separate from route logic.
Introduced in PR2 to reduce conditional clutter inside routes.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from app.models.pet import Pet


class PetPresenter:
    """Builds view-specific representations of a Pet.

    Views:
      - mypage: full personal profile subset
      - petcare: minimal identity (future extension)
      - social: public info + derived metrics (age_months, post_count)
    """

    @staticmethod
    def _base(pet: Pet) -> Dict[str, Any]:
        return {
            "pet_id": pet.pet_id,
            "name": pet.name,
            "profile_image_url": pet.profile_image_url,
            "is_verified": pet.is_verified,
        }

    @staticmethod
    def _add_identity(pet: Pet, data: Dict[str, Any]):
        data.update({
            "birthdate": pet.birthdate,
            "gender": pet.gender.value if pet.gender else None,
            "breed": pet.breed,
        })

    @staticmethod
    def _maybe_age(pet: Pet, data: Dict[str, Any]):
        if pet.birthdate:
            today = date.today()
            age_months = (today.year - pet.birthdate.year) * 12 + (today.month - pet.birthdate.month)
            data["age_months"] = age_months

    @classmethod
    def build_view_response(
        cls,
        pet: Pet,
        view: str,
        user_stats_service: Optional[Any] = None,
        target_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        data = cls._base(pet)

        if view in ("mypage", "social"):
            cls._add_identity(pet, data)

        if view == "social":
            cls._maybe_age(pet, data)
            # Use user_stats service instead of posts service (aggregation responsibility).
            if user_stats_service and target_user_id:
                try:
                    stats = user_stats_service.get_user_stats(target_user_id)
                    data["post_count"] = stats.get("post_count", 0)
                except Exception:
                    data["post_count"] = 0
            else:
                data["post_count"] = 0

        return data

__all__ = ["PetPresenter"]
