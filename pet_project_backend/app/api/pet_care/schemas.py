"""Schema aggregator for pet_care domain.

The OpenAPI builder scans for *schemas.py at the domain root. Because
pet_care splits schemas into nested subpackages (settings, records), this
module re-exports them so automatic harvesting picks them up.
"""

from .settings.schemas import PetCareSettingsSchema  # noqa: F401
from .records.schemas import (  # noqa: F401
    CareRecordCreateSchema,
    CareRecordUpdateSchema,
    RecordResponseSchema,
    DailyRecordsResponseSchema,
)

__all__ = [
    "PetCareSettingsSchema",
    "CareRecordCreateSchema",
    "CareRecordUpdateSchema",
    "RecordResponseSchema",
    "DailyRecordsResponseSchema",
]
