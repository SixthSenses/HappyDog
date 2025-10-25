"""Pet Onboarding Service.

Handles the complete pet onboarding process including:
- Pet profile creation
- Initial pet care settings setup
- User-pet relationship establishment

This service coordinates multi-step onboarding while ensuring atomicity.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Dict, Any
from firebase_admin import firestore
from firebase_admin.firestore import Transaction

from app.models.pet import Pet, PetGender
from app.utils.datetime_utils import DateTimeUtils


class PetOnboardingService:
    """Coordinates complete pet onboarding process with transaction boundaries.
    
    This service ensures atomic onboarding: if any step fails, all changes are rolled back.
    """

    def __init__(self, db_client, pet_care_setting_service):
        """Initialize onboarding service with dependencies.
        
        Args:
            db_client: Firestore client
            pet_care_setting_service: Service for creating initial pet care settings
        """
        self.db = db_client
        self.pet_care_setting_service = pet_care_setting_service
        
        if self.db is None:
            self.pets_ref = None
            self.users_ref = None
            logging.info("PetOnboardingService initialized without Firestore (docs mode)")
        else:
            self.pets_ref = self.db.collection('pets')
            self.users_ref = self.db.collection('users')
            logging.info("PetOnboardingService initialized")

    def onboard_pet(self, user_id: str, pet_data: Dict[str, Any]) -> Pet:
        """Complete pet onboarding with atomic transaction.
        
        Steps performed atomically:
        1. Verify user exists and has no existing pet
        2. Create pet profile
        3. Update user with pet relationship
        4. Create initial pet care settings
        
        Args:
            user_id: The owner's user ID
            pet_data: Pet registration data (name, gender, breed, birthdate, etc.)
            
        Returns:
            Created Pet object
            
        Raises:
            ValueError: If user already has a pet or user not found
            RuntimeError: If onboarding transaction fails
        """
        if self.db is None:
            # DOCS_MODE: return synthetic pet
            return Pet(
                pet_id=str(uuid.uuid4()),
                user_id=user_id,
                name=pet_data['name'],
                gender=PetGender(pet_data['gender']),
                breed=pet_data['breed'],
                birthdate=pet_data['birthdate'],
                fur_color=pet_data.get('fur_color'),
                health_concerns=pet_data.get('health_concerns', [])
            )
        
        user_ref = self.users_ref.document(user_id)
        pet_id = str(uuid.uuid4())
        pet_ref = self.pets_ref.document(pet_id)
        transaction = self.db.transaction()

        @firestore.transactional
        def _onboard_in_transaction(transaction: Transaction):
            # Step 1: Verify user and single-pet policy
            user_doc = user_ref.get(transaction=transaction)
            if not user_doc.exists:
                raise ValueError("사용자를 찾을 수 없습니다.")
            
            user_data = user_doc.to_dict() or {}
            if user_data.get('has_pet', False):
                raise ValueError("이미 등록된 반려동물이 있습니다.")
            
            # Step 2: Create pet profile
            new_pet = Pet(
                pet_id=pet_id,
                user_id=user_id,
                name=pet_data['name'],
                gender=PetGender(pet_data['gender']),
                breed=pet_data['breed'],
                birthdate=pet_data['birthdate'],
                fur_color=pet_data.get('fur_color'),
                health_concerns=pet_data.get('health_concerns', [])
            )
            
            # Convert to Firestore format
            pet_dict = asdict(new_pet)
            pet_dict['gender'] = new_pet.gender.value
            firestore_data = DateTimeUtils.for_firestore(pet_dict)
            
            # Step 3: Atomic writes - pet creation + user update
            transaction.set(pet_ref, firestore_data)
            transaction.update(user_ref, {
                'has_pet': True,
                'pet_id': pet_id
            })
            
            # Step 4: Create initial pet care settings
            # Note: current_weight=0.0 as weight field is removed from profile
            self.pet_care_setting_service.create_initial_settings_transactional(
                transaction,
                pet_id=pet_id,
                gender=new_pet.gender.value,
                breed=new_pet.breed,
                current_weight=0.0  # Fallback, actual weight will be tracked in pet_care records
            )
            
            logging.info(f"Pet onboarding completed: pet_id={pet_id}, user_id={user_id}")
            return new_pet

        try:
            return _onboard_in_transaction(transaction)
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logging.error(f"Pet onboarding failed for user {user_id}: {e}", exc_info=True)
            raise RuntimeError(f"반려동물 등록 중 오류가 발생했습니다: {str(e)}")

    def validate_onboarding_data(self, pet_data: Dict[str, Any]) -> None:
        """Validate pet onboarding data before transaction.
        
        Args:
            pet_data: Pet registration data
            
        Raises:
            ValueError: If data is invalid
        """
        required_fields = ['name', 'gender', 'breed', 'birthdate']
        for field in required_fields:
            if field not in pet_data or not pet_data[field]:
                raise ValueError(f"필수 필드 '{field}'가 누락되었습니다.")
        
        # Validate gender
        try:
            PetGender(pet_data['gender'])
        except (ValueError, KeyError):
            raise ValueError("유효하지 않은 성별입니다.")
