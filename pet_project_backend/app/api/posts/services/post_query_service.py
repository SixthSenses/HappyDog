"""Post Query Service.

Handles data retrieval for post creation and display,
separating query logic from core CRUD operations.
"""
from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from app.models.post import Author, PetInfo
from app.services.storage_interfaces import StorageUrlProvider


class PostQueryService:
    """Query service for post-related data retrieval.
    
    Focuses on fetching author and pet information needed for posts,
    separated from CRUD operations for better testability and maintenance.
    """

    def __init__(self, db_client=None, storage_service: Optional[StorageUrlProvider] = None):
        """Initialize query service with dependencies.
        
        Args:
            db_client: Optional Firestore client
            storage_service: Optional storage service for URL conversion
        """
        self.db = db_client
        self.storage_service = storage_service
        
        if self.db is None:
            self.users_ref = None
            self.pets_ref = None
            logging.info("PostQueryService initialized without Firestore (docs mode)")
        else:
            self.users_ref = self.db.collection('users')
            self.pets_ref = self.db.collection('pets')

    def get_author_snapshot(self, user_id: str) -> Optional[Author]:
        """Get author information snapshot for post creation.
        
        Args:
            user_id: User identifier
            
        Returns:
            Author object or None if user not found
        """
        if self.users_ref is None:
            # DOCS_MODE: return synthetic author
            return Author(user_id=user_id, nickname="demo_user")
        
        try:
            user_doc = self.users_ref.document(user_id).get()
            if not user_doc.exists:
                logging.warning(f"User not found: {user_id}")
                return None
            
            user_data = user_doc.to_dict()
            return Author(
                user_id=user_id,
                nickname=user_data.get("nickname", "Unknown")
            )
        except Exception as e:
            logging.error(f"Failed to get author snapshot for user {user_id}: {e}", exc_info=True)
            return None

    def get_pet_snapshot(self, user_id: str) -> Optional[PetInfo]:
        """Get pet information snapshot for post creation.
        
        Retrieves the first pet owned by the user for snapshot embedding.
        
        Args:
            user_id: Owner's user identifier
            
        Returns:
            PetInfo object or None if no pet found
        """
        if self.pets_ref is None:
            # DOCS_MODE: return synthetic pet
            return PetInfo(
                pet_id="demo_pet",
                name="Demo",
                breed="Unknown",
                birthdate=None,
                profile_image_url=None,
                is_verified=False
            )
        
        try:
            pet_docs = self.pets_ref.where('user_id', '==', user_id).limit(1).get()
            if not pet_docs:
                logging.warning(f"No pet found for user: {user_id}")
                return None
            
            pet_raw = pet_docs[0]
            pet_data = pet_raw.to_dict()
            
            # Ensure pet_id is set
            if not pet_data.get("pet_id"):
                pet_data["pet_id"] = pet_raw.id
            
            # Convert profile image URL if needed
            profile_image_url = self._convert_profile_image_url(pet_data.get("profile_image_url"))
            
            return PetInfo(
                pet_id=pet_data.get("pet_id"),
                name=pet_data.get("name"),
                breed=pet_data.get("breed"),
                birthdate=pet_data.get("birthdate"),
                profile_image_url=profile_image_url,
                is_verified=pet_data.get("is_verified", False)
            )
        except Exception as e:
            logging.error(f"Failed to get pet snapshot for user {user_id}: {e}", exc_info=True)
            return None

    def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get complete user information.
        
        Args:
            user_id: User identifier
            
        Returns:
            User data dictionary or None
        """
        if self.users_ref is None:
            return None
        
        try:
            user_doc = self.users_ref.document(user_id).get()
            if user_doc.exists:
                return user_doc.to_dict()
            return None
        except Exception as e:
            logging.error(f"Failed to get user info for {user_id}: {e}", exc_info=True)
            return None

    def _convert_profile_image_url(self, profile_image_url: Optional[str]) -> Optional[str]:
        """Convert relative path to full URL for pet profile image.
        
        Args:
            profile_image_url: Pet profile image path or URL
            
        Returns:
            Firebase Storage URL or None
        """
        if not profile_image_url:
            return None
        
        # Already a full URL
        if profile_image_url.startswith('https://'):
            return profile_image_url
        
        # No storage service available
        if not self.storage_service:
            logging.warning(f"StorageService not available, returning original path: {profile_image_url}")
            return profile_image_url
        
        # Convert relative path to URL
        try:
            return self.storage_service.get_public_url(profile_image_url)
        except Exception as e:
            logging.warning(f"Failed to convert profile image URL: {e}")
            return profile_image_url
