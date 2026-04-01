# app/services/upload_path_strategies.py
"""
Upload path strategy pattern for storage routing (Phase 2-4: OCP compliance).

Strategy Pattern:
- Each upload type has a dedicated strategy class
- New upload types can be added without modifying StorageService
- Centralized path mapping logic with clear documentation

Usage:
    strategy = upload_type_registry.get("post_image")
    path = strategy.generate_path(user_id="user123", filename="photo.jpg")
"""

import uuid
import logging
from typing import Protocol, Dict
from abc import abstractmethod


class UploadPathStrategy(Protocol):
    """
    Protocol defining the interface for upload path generation strategies.
    
    Each upload type (post_image, pet_profile, etc.) should implement this protocol
    to provide a consistent way to generate storage paths while allowing
    custom logic per upload type.
    """
    
    @property
    @abstractmethod
    def upload_type(self) -> str:
        """Return the upload type identifier (e.g., 'post_image')."""
        ...
    
    @abstractmethod
    def generate_path(self, user_id: str, filename: str) -> str:
        """
        Generate the full storage path for the given upload.
        
        Args:
            user_id: User ID from JWT (used for user-scoped paths)
            filename: Original filename (used for extension extraction)
        
        Returns:
            Full storage path (e.g., 'posts/user123/uuid.jpg')
        """
        ...


class PostImagePathStrategy:
    """Strategy for post image uploads."""
    
    @property
    def upload_type(self) -> str:
        return "post_image"
    
    def generate_path(self, user_id: str, filename: str) -> str:
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        return f"posts/{user_id}/{unique_filename}"


class PetProfilePathStrategy:
    """Strategy for pet profile image uploads."""
    
    @property
    def upload_type(self) -> str:
        return "pet_profile"
    
    def generate_path(self, user_id: str, filename: str) -> str:
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        return f"pet_profiles/{user_id}/{unique_filename}"


class PetNosePrintPathStrategy:
    """Strategy for pet nose print (biometric) uploads."""
    
    @property
    def upload_type(self) -> str:
        return "pet_nose_print"
    
    def generate_path(self, user_id: str, filename: str) -> str:
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        # Nose prints start in staging, promoted to verified after ML processing
        return f"nose_prints_staging/{user_id}/{unique_filename}"


class EyeAnalysisPathStrategy:
    """Strategy for eye health analysis image uploads."""
    
    @property
    def upload_type(self) -> str:
        return "eye_analysis"
    
    def generate_path(self, user_id: str, filename: str) -> str:
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        return f"eye_analysis_images/{user_id}/{unique_filename}"


class CartoonSourcePathStrategy:
    """Strategy for cartoon source image uploads."""
    
    @property
    def upload_type(self) -> str:
        return "cartoon_source_image"
    
    def generate_path(self, user_id: str, filename: str) -> str:
        extension = filename.split('.')[-1] if '.' in filename else ''
        unique_filename = f"{uuid.uuid4()}.{extension}"
        return f"cartoon_sources/{user_id}/{unique_filename}"


# Registry: maps upload_type strings to strategy instances
upload_type_registry: Dict[str, UploadPathStrategy] = {
    "post_image": PostImagePathStrategy(),
    "pet_profile": PetProfilePathStrategy(),
    "pet_nose_print": PetNosePrintPathStrategy(),
    "eye_analysis": EyeAnalysisPathStrategy(),
    "cartoon_source_image": CartoonSourcePathStrategy(),
}


def get_upload_strategy(upload_type: str) -> UploadPathStrategy:
    """
    Retrieve the path generation strategy for the given upload type.
    
    Args:
        upload_type: Upload type identifier (e.g., 'post_image')
    
    Returns:
        The corresponding UploadPathStrategy instance
    
    Raises:
        ValueError: If upload_type is not registered
    """
    strategy = upload_type_registry.get(upload_type)
    if not strategy:
        raise ValueError(
            f"'{upload_type}'은(는) 유효한 업로드 타입이 아닙니다. "
            f"지원되는 타입: {list(upload_type_registry.keys())}"
        )
    return strategy
