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
from app.services.storage_service import StorageService
from app.api.pet_care.settings.services import PetCareSettingService


class PetProfileService:
    """Service for managing pet profile CRUD operations and storage integration."""

    def __init__(self, storage_service: StorageService, pet_care_setting_service: PetCareSettingService):
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')
        self.storage_service = storage_service
        self.pet_care_setting_service = pet_care_setting_service
        logging.info("PetProfileService initialized with storage and settings services.")

    # ============= Core CRUD Operations =============

    def get_pet_by_id_and_owner(self, pet_id: str, user_id: str) -> Optional[Pet]:
        """Get pet information and convert to Pet object.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            
        Returns:
            Pet object if found and owned by user, None otherwise
        """
        doc = self.pets_ref.document(pet_id).get()
        if doc.exists:
            pet_data = doc.to_dict() or {}
            # Legacy compatibility: fill pet_id if missing
            if 'pet_id' not in pet_data or not pet_data.get('pet_id'):
                pet_data['pet_id'] = doc.id
            if pet_data.get('user_id') == user_id:
                return Pet.from_dict(pet_data)
        return None

    def get_first_pet_by_owner(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the first pet owned by user using optimized User document lookup.
        
        Args:
            user_id: The owner's user ID
            
        Returns:
            Pet data as dict if found, None otherwise
        """
        try:
            # First check user document for pet_id (O(1) lookup)
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            if not user_doc.exists:
                return None
            
            user_data = user_doc.to_dict() or {}
            pet_id = user_data.get('pet_id')
            
            if not pet_id:
                return None
            
            # Direct pet document lookup (O(1))
            pet_doc = self.pets_ref.document(pet_id).get()
            if not pet_doc.exists:
                logging.warning(f"Inconsistent data: User {user_id} has pet_id {pet_id} but pet not found")
                return None
            
            data = pet_doc.to_dict() or {}
            # Ensure pet_id is present for legacy compatibility
            if 'pet_id' not in data or not data.get('pet_id'):
                data['pet_id'] = pet_doc.id
            
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
        try:
            # Use optimized get_first_pet_by_owner method
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
        doc = self.pets_ref.document(pet_id).get()
        if not doc.exists:
            raise FileNotFoundError("해당 ID의 반려동물을 찾을 수 없습니다.")
        data = doc.to_dict() or {}
        # Legacy compatibility: fill pet_id if missing
        if 'pet_id' not in data or not data.get('pet_id'):
            data['pet_id'] = doc.id
        return data

    def register_pet(self, user_id: str, pet_data: Dict[str, Any]) -> Pet:
        """Register new pet with atomic single-pet policy enforcement.
        
        Uses User document-based control for better performance and consistency.
        All operations are performed within a single Firestore transaction.
        
        Args:
            user_id: The owner's user ID
            pet_data: Pet registration data
            
        Returns:
            Created Pet object
            
        Raises:
            ValueError: If user already has a pet or user not found
            RuntimeError: If registration transaction fails
        """
        user_ref = self.db.collection('users').document(user_id)
        pet_id = str(uuid.uuid4())
        pet_ref = self.pets_ref.document(pet_id)
        transaction = self.db.transaction()

        @firestore.transactional
        def _register_in_transaction(transaction: Transaction):
            # Atomic check: verify user exists and has no pet
            user_doc = user_ref.get(transaction=transaction)
            if not user_doc.exists:
                raise ValueError("사용자를 찾을 수 없습니다.")
            
            user_data = user_doc.to_dict() or {}
            if user_data.get('has_pet', False):
                raise ValueError("이미 등록된 반려동물이 있습니다.")
            
            # Create new pet
            new_pet = Pet(
                pet_id=pet_id, 
                user_id=user_id,
                name=pet_data['name'], 
                gender=PetGender(pet_data['gender']),
                breed=pet_data['breed'], 
                birthdate=pet_data['birthdate'],
                initial_weight=pet_data['current_weight'],
                fur_color=pet_data.get('fur_color'),
                health_concerns=pet_data.get('health_concerns', [])
            )
            
            # Convert to Firestore format
            pet_dict = asdict(new_pet)
            pet_dict['gender'] = new_pet.gender.value
            firestore_data = DateTimeUtils.for_firestore(pet_dict)
            
            # Atomic operations: create pet + update user
            transaction.set(pet_ref, firestore_data)
            transaction.update(user_ref, {
                'has_pet': True,
                'pet_id': pet_id
            })
            
            # Create initial pet care settings
            self.pet_care_setting_service.create_initial_settings_transactional(
                transaction, pet_id=pet_id, gender=new_pet.gender.value,
                breed=new_pet.breed, current_weight=new_pet.initial_weight
            )
            
            return new_pet

        try:
            return _register_in_transaction(transaction)
        except ValueError:
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            logging.error(f"Pet registration transaction failed for user {user_id}: {e}", exc_info=True)
            raise RuntimeError("반려동물 등록에 실패했습니다. 다시 시도해주세요.")

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
        pet_ref = self.pets_ref.document(pet_id)
        doc = pet_ref.get()
        if not doc.exists or doc.to_dict().get('user_id') != user_id:
            raise PermissionError("프로필을 수정할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        if not update_data:
            raise ValueError("수정할 데이터가 제공되지 않았습니다.")
            
        pet_ref.update(update_data)
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

    def calculate_profile_completion(self, pet: Pet) -> float:
        """Calculate profile completion percentage.
        
        Args:
            pet: Pet object
            
        Returns:
            Completion percentage (0.0 - 1.0)
        """
        required_fields = ['name', 'gender', 'breed', 'birthdate', 'initial_weight']
        optional_fields = ['fur_color', 'health_concerns']
        
        completed_required = sum(1 for field in required_fields if getattr(pet, field, None))
        completed_optional = sum(1 for field in optional_fields if getattr(pet, field, None))
        
        total_fields = len(required_fields) + len(optional_fields)
        completed_fields = completed_required + completed_optional
        
        return completed_fields / total_fields if total_fields > 0 else 0.0

    # ============= Storage Integration =============

    def update_profile_image(self, pet_id: str, user_id: str, file_path: str) -> str:
        """Update pet profile image.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            file_path: Storage path of the uploaded image
            
        Returns:
            Public URL of the uploaded image
            
        Raises:
            PermissionError: If pet not found or user not authorized
        """
        # Verify ownership
        if not self.get_pet_by_id_and_owner(pet_id, user_id):
            raise PermissionError("프로필 이미지를 수정할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        
        # Make image public and get URL
        public_url = self.storage_service.make_public_and_get_url(file_path)
        
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
