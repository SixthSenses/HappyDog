"""Services package initialization for pets domain.

Provides clean import access to the specialized services:
- PetProfileService: Core CRUD operations and profile management
- PetBiometricService: ML pipeline integration and biometric analysis
- PetService: Facade coordinator maintaining backward compatibility
"""

from .pet_profile_service import PetProfileService
from .pet_biometric_service import PetBiometricService, BiometricAnalysisResult

__all__ = [
    'PetProfileService',
    'PetBiometricService', 
    'BiometricAnalysisResult'
]
