"""Pet Profile Service - Pure CRUD Operations.

This service handles core pet profile management including:
- Pet creation, reading, updating, deletion
- Profile validation and business rules
- Storage integration for profile images
- Settings service coordination for initial setup

Separated from ML/biometric concerns for clean architecture.
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, Optional
from dataclasses import asdict
from firebase_admin import firestore
from firebase_admin.firestore import Transaction

from app.models.pet import Pet, PetGender
from app.utils.datetime_utils import DateTimeUtils
from app.services.storage_interfaces import StorageUrlProvider
from app.api.pet_care.settings.services import PetCareSettingService


class PetProfileService:
    """Service for managing pet profile CRUD operations and storage integration.

    DOCS_MODE: Firestore access skipped, placeholder synthetic data returned.
    """

    def __init__(self, storage_service: StorageUrlProvider, pet_care_setting_service: PetCareSettingService, db_client=None, onboarding_service=None):
        self.db = db_client
        self.pets_ref = self.db.collection('pets') if self.db else None
        self.storage_service = storage_service
        self.pet_care_setting_service = pet_care_setting_service
        
        # Phase 2: Delegate onboarding to specialized service
        self.onboarding_service = onboarding_service
        if onboarding_service is None:
            # Backward compatibility: create onboarding service internally
            from .pet_onboarding_service import PetOnboardingService
            self.onboarding_service = PetOnboardingService(db_client, pet_care_setting_service)
        
        if self.db is None:
            logging.info("PetProfileService initialized without Firestore client (docs mode)")
        else:
            logging.info("PetProfileService initialized successfully")

    # ============= Core CRUD Operations =============

    def _ensure_full_profile_image_url(self, pet_data: Dict[str, Any]) -> None:
        """
        profile_image_url이 상대 경로인 경우 전체 URL로 변환합니다.
        
        Note:
            - 레거시 데이터 지원: DB에 상대 경로로 저장된 기존 데이터 처리
            - 새로운 데이터는 update_pet_profile_image에서 이미 URL로 변환되어 저장됨
            - URL 변환 실패 시 원본 유지 (에러 발생 안 함)
        """
        if not pet_data or 'profile_image_url' not in pet_data:
            return
        
        profile_image_url = pet_data.get('profile_image_url')
        if not profile_image_url or not self.storage_service:
            return
        
        # 상대 경로인지 확인 (https://로 시작하지 않으면 상대 경로)
        if not profile_image_url.startswith('https://'):
            try:
                full_url = self.storage_service.get_public_url(profile_image_url)
                pet_data['profile_image_url'] = full_url
            except Exception as e:
                logging.warning(f"Profile image URL 변환 실패 (fallback to original): {profile_image_url} - {e}")

    def get_pet_by_id_and_owner(self, pet_id: str, user_id: str) -> Optional[Pet]:
        """Get pet information and convert to Pet object.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            
        Returns:
            Pet object if found and owned by user, None otherwise
        """
        if self.pets_ref is None:
            return None
        doc = self.pets_ref.document(pet_id).get()
        if doc.exists:
            pet_data = doc.to_dict() or {}
            # Legacy compatibility: fill pet_id if missing
            if 'pet_id' not in pet_data or not pet_data.get('pet_id'):
                pet_data['pet_id'] = doc.id
            if pet_data.get('user_id') == user_id:
                # 기존 상대 경로 데이터를 전체 URL로 변환
                self._ensure_full_profile_image_url(pet_data)
                return Pet.from_dict(pet_data)
        return None

    def get_first_pet_by_owner(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the first pet owned by user using optimized User document lookup.
        
        Args:
            user_id: The owner's user ID
            
        Returns:
            Pet data as dict if found, None otherwise
        """
        if self.pets_ref is None or self.db is None:
            return None
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            if not user_doc.exists:
                return None
            user_data = user_doc.to_dict() or {}
            pet_id = user_data.get('pet_id')
            if not pet_id:
                return None
            pet_doc = self.pets_ref.document(pet_id).get()
            if not pet_doc.exists:
                logging.warning(f"Inconsistent data: User {user_id} has pet_id {pet_id} but pet not found")
                return None
            data = pet_doc.to_dict() or {}
            if 'pet_id' not in data or not data.get('pet_id'):
                data['pet_id'] = pet_doc.id
            # 기존 상대 경로 데이터를 전체 URL로 변환
            self._ensure_full_profile_image_url(data)
            return data
        except Exception as e:
            logging.error(f"get_first_pet_by_owner failed (user_id={user_id}): {e}", exc_info=True)
            raise

    def get_user_pet_profile(self, user_id: str) -> Optional[Pet]:
        """Get the user's pet profile as Pet object using optimized lookup.
        
        Args:
            user_id: The owner's user ID
            
        Returns:
            Pet object if found, None otherwise
        """
        if self.pets_ref is None:
            return None
        try:
            pet_data = self.get_first_pet_by_owner(user_id)
            if not pet_data:
                return None
            return Pet.from_dict(pet_data)
        except Exception as e:
            logging.error(f"get_user_pet_profile failed (user_id={user_id}): {e}", exc_info=True)
            raise

    def get_pet_profile(self, pet_id: str, user_id: str) -> Pet:
        """Get pet profile for owner (authorization required).
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            
        Returns:
            Pet object
            
        Raises:
            PermissionError: If pet not found or user not authorized
        """
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("프로필을 조회할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        return pet_info

    def get_pet_profile_dict(self, pet_id: str, user_id: str) -> Dict[str, Any]:
        """Get pet profile as dictionary (authorization required).
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            
        Returns:
            Pet data as dictionary
        """
        pet = self.get_pet_profile(pet_id, user_id)
        return self._pet_to_dict(pet)

    def get_public_pet_profile(self, pet_id: str) -> Dict[str, Any]:
        """Get public pet profile without ownership check.
        
        Args:
            pet_id: The pet's unique identifier
            
        Returns:
            Pet data as dictionary
            
        Raises:
            FileNotFoundError: If pet not found
        """
        if self.pets_ref is None:
            # Return synthetic placeholder
            return {
                'pet_id': pet_id,
                'user_id': 'placeholder',
                'name': 'ExamplePet',
                'gender': 'MALE',
                'breed': 'Unknown',
                'birthdate': '2020-01-01',
                'health_concerns': []
            }
        doc = self.pets_ref.document(pet_id).get()
        if not doc.exists:
            raise FileNotFoundError("해당 ID의 반려동물을 찾을 수 없습니다.")
        data = doc.to_dict() or {}
        if 'pet_id' not in data or not data.get('pet_id'):
            data['pet_id'] = doc.id
        return data

    def register_pet(self, user_id: str, pet_data: Dict[str, Any]) -> Pet:
        """Register new pet via onboarding service (delegated).
        
        Phase 2: Delegates complete onboarding to specialized PetOnboardingService.
        
        Args:
            user_id: The owner's user ID
            pet_data: Pet registration data
            
        Returns:
            Created Pet object
            
        Raises:
            ValueError: If user already has a pet or user not found
            RuntimeError: If registration transaction fails
        """
        # Delegate complete onboarding to specialized service
        return self.onboarding_service.onboard_pet(user_id, pet_data)

    def update_pet_profile(self, pet_id: str, user_id: str, update_data: Dict[str, Any]) -> Pet:
        """Update pet profile information partially.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            update_data: Data to update
            
        Returns:
            Updated Pet object
            
        Raises:
            PermissionError: If pet not found or user not authorized
            ValueError: If no update data provided
            RuntimeError: If unable to retrieve updated pet
        """
        if self.pets_ref is None:
            return Pet(
                pet_id=pet_id,
                user_id=user_id,
                name=update_data.get('name', 'ExamplePet'),
                gender=PetGender(update_data.get('gender', 'MALE')),
                breed=update_data.get('breed', 'Unknown'),
                birthdate=update_data.get('birthdate', '2020-01-01'),
                fur_color=update_data.get('fur_color'),
                health_concerns=update_data.get('health_concerns', [])
            )
        pet_ref = self.pets_ref.document(pet_id)
        doc = pet_ref.get()
        if not doc.exists or doc.to_dict().get('user_id') != user_id:
            raise PermissionError("프로필을 수정할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        if not update_data:
            raise ValueError("수정할 데이터가 제공되지 않았습니다.")
        
        # Firestore 저장을 위해 date/datetime 객체를 Firestore Timestamp로 변환
        firestore_data = DateTimeUtils.for_firestore(update_data)
            
        pet_ref.update(firestore_data)
        logging.info(f"Pet profile updated for {pet_id} with fields: {list(update_data.keys())}")
        
        # Return updated Pet object
        updated_pet = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not updated_pet:
            raise RuntimeError("업데이트된 반려동물 정보를 조회할 수 없습니다.")
        return updated_pet

    # ============= Business Rules & Validation =============

    def validate_single_pet_policy(self, user_id: str) -> bool:
        """Check if user can register another pet using User document.
        
        Args:
            user_id: The user's ID
            
        Returns:
            True if user can register a pet, False otherwise
        """
        if self.db is None:
            return True
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            if not user_doc.exists:
                return False
            user_data = user_doc.to_dict() or {}
            return not user_data.get('has_pet', False)
        except Exception as e:
            logging.error(f"Single pet policy check failed for user {user_id}: {e}", exc_info=True)
            return False

    # 제거: 사용되지 않는 프로필 완료도 계산 로직 (weight 제거와 함께 비활성화)

    # ============= Storage Integration =============

    def update_profile_image(self, pet_id: str, user_id: str, file_path: str) -> str:
        """Update pet profile image.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            file_path: Storage path of the uploaded image (relative path)
            
        Returns:
            Firebase Storage URL (with token)
            
        Raises:
            PermissionError: If pet not found or user not authorized
            FileNotFoundError: If file does not exist in Storage
        """
        # Verify ownership
        if not self.get_pet_by_id_and_owner(pet_id, user_id):
            raise PermissionError("프로필 이미지를 수정할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        
        # Get Firebase Storage URL with token
        public_url = self.storage_service.get_public_url(file_path)
        
        # Update profile with image URL
        self.update_pet_profile(pet_id, user_id, {'profile_image_url': public_url})
        
        logging.info(f"Profile image updated for pet {pet_id}")
        return public_url

    # ============= Utility Methods =============

    def _pet_to_dict(self, pet: Pet) -> Dict[str, Any]:
        """Convert Pet object to dictionary.
        
        Args:
            pet: Pet object
            
        Returns:
            Pet data as dictionary
        """
        pet_dict = asdict(pet)
        pet_dict['gender'] = pet.gender.value
        return pet_dict
