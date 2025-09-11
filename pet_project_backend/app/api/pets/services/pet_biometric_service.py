"""Pet Biometric Service - ML Pipeline Integration.

This service handles biometric analysis including:
- Nose print registration and verification
- Eye pattern analysis for health screening
- ML pipeline abstraction and error handling
- Asynchronous processing support (future)
- Graceful degradation when ML services unavailable

Separated from profile management for clean architecture.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from firebase_admin import firestore
from firebase_admin.firestore import Transaction

from app.services.storage_service import StorageService
from app.services.firestore_service import save_analysis_result
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline
from eyes_models.eyes_lib.inference import EyeAnalyzer


@dataclass
class BiometricAnalysisResult:
    """Standardized result format for biometric analysis."""
    success: bool
    confidence: Optional[float] = None
    features: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    analysis_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PetBiometricService:
    """Service for managing pet biometric analysis and ML pipeline integration."""

    def __init__(self, storage_service: StorageService, 
                 nose_pipeline: Optional[NosePrintPipeline] = None,
                 eye_analyzer: Optional[EyeAnalyzer] = None):
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')
        self.storage_service = storage_service
        self.nose_pipeline = nose_pipeline
        self.eye_analyzer = eye_analyzer
        
        # Service availability flags
        self.nose_analysis_available = nose_pipeline is not None
        self.eye_analysis_available = eye_analyzer is not None
        
        logging.info(
            f"PetBiometricService initialized. "
            f"Nose analysis: {'available' if self.nose_analysis_available else 'unavailable'}, "
            f"Eye analysis: {'available' if self.eye_analysis_available else 'unavailable'}"
        )

    # ============= Service Health Checks =============

    def is_nose_analysis_available(self) -> bool:
        """Check if nose print analysis service is available."""
        return self.nose_analysis_available

    def is_eye_analysis_available(self) -> bool:
        """Check if eye pattern analysis service is available."""
        return self.eye_analysis_available

    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status for health checks."""
        return {
            'nose_analysis': {
                'available': self.nose_analysis_available,
                'service': 'NosePrintPipeline' if self.nose_pipeline else None
            },
            'eye_analysis': {
                'available': self.eye_analysis_available,
                'service': 'EyeAnalyzer' if self.eye_analyzer else None
            },
            'storage': {
                'available': self.storage_service is not None,
                'service': 'StorageService'
            }
        }

    # ============= Nose Print Analysis =============

    def register_nose_print_for_pet(self, pet_id: str, user_id: str, file_path: str, 
                                   pet_verification_status: bool = False) -> BiometricAnalysisResult:
        """Register and analyze nose print for pet verification.
        
        Args:
            pet_id: The pet's unique identifier
            user_id: The owner's user ID for authorization
            file_path: Storage path of the nose print image
            pet_verification_status: Current verification status of the pet
            
        Returns:
            BiometricAnalysisResult with analysis outcome
        """
        if not self.nose_analysis_available:
            return BiometricAnalysisResult(
                success=False,
                error_message="비문 분석 서비스를 사용할 수 없습니다. 나중에 다시 시도해주세요."
            )

        # Check if pet is already verified
        if pet_verification_status:
            logging.info(f"Pet {pet_id} is already verified. Skipping nose print registration.")
            return BiometricAnalysisResult(
                success=True,
                metadata={"status": "ALREADY_VERIFIED", "message": "이미 비문 인증이 완료된 반려동물입니다."}
            )
        
        logging.info(f"Starting nose print registration for pet {pet_id}")
        
        try:
            # Process nose print image
            result = self.nose_pipeline.process_image(self.storage_service, file_path)
            status = result.get("status")

            if status == "SUCCESS":
                logging.info(f"Nose print processing successful for pet {pet_id}. Updating database...")
                
                # Transactional database update
                transaction = self.db.transaction()
                
                @firestore.transactional
                def _update_nose_print_transactional(transaction: Transaction):
                    public_url = self.storage_service.make_public_and_get_url(file_path)
                    update_data = {
                        "is_verified": True,
                        "nose_print_url": public_url,
                        "faiss_id": result['faiss_id']
                    }
                    transaction.update(self.pets_ref.document(pet_id), update_data)
                    return public_url
                
                try:
                    public_url = _update_nose_print_transactional(transaction)
                    # Add vector to index after successful DB update
                    self.nose_pipeline.add_vector_to_index(result['vector'])
                    logging.info(f"Nose print registration completed successfully for pet {pet_id}")
                    
                    return BiometricAnalysisResult(
                        success=True,
                        confidence=result.get('confidence'),
                        features={'faiss_id': result['faiss_id'], 'nose_print_url': public_url},
                        metadata={"status": "SUCCESS", "message": "비문이 성공적으로 등록 및 인증되었습니다."}
                    )
                except Exception as e:
                    logging.error(f"Failed to update nose print data for pet {pet_id}: {e}")
                    return BiometricAnalysisResult(
                        success=False,
                        error_message="비문 등록 중 데이터베이스 오류가 발생했습니다."
                    )
            else:
                logging.warning(f"Nose print processing failed for pet {pet_id}. Status: {status}")
                return BiometricAnalysisResult(
                    success=False,
                    error_message=result.get('message', '비문 분석에 실패했습니다.'),
                    metadata=result
                )
                
        except Exception as e:
            logging.error(f"Nose print analysis failed for pet {pet_id}: {e}", exc_info=True)
            return BiometricAnalysisResult(
                success=False,
                error_message=f"비문 분석 중 오류가 발생했습니다: {str(e)}"
            )

    def verify_nose_print(self, pet_id: str, file_path: str) -> BiometricAnalysisResult:
        """Verify nose print against registered prints.
        
        Args:
            pet_id: The pet's unique identifier
            file_path: Storage path of the nose print image for verification
            
        Returns:
            BiometricAnalysisResult with verification outcome
        """
        if not self.nose_analysis_available:
            return BiometricAnalysisResult(
                success=False,
                error_message="비문 검증 서비스를 사용할 수 없습니다."
            )

        try:
            # Process verification image
            result = self.nose_pipeline.verify_image(self.storage_service, file_path)
            
            return BiometricAnalysisResult(
                success=result.get("status") == "MATCH",
                confidence=result.get('confidence'),
                metadata=result
            )
        except Exception as e:
            logging.error(f"Nose print verification failed for pet {pet_id}: {e}", exc_info=True)
            return BiometricAnalysisResult(
                success=False,
                error_message=f"비문 검증 중 오류가 발생했습니다: {str(e)}"
            )

    # ============= Eye Pattern Analysis =============

    def analyze_eye_image_for_pet(self, user_id: str, pet_id: str, file_path: str) -> BiometricAnalysisResult:
        """Analyze eye image for health screening.
        
        Args:
            user_id: The owner's user ID for authorization
            pet_id: The pet's unique identifier
            file_path: Storage path of the eye image
            
        Returns:
            BiometricAnalysisResult with analysis outcome
        """
        if not self.eye_analysis_available:
            return BiometricAnalysisResult(
                success=False,
                error_message="안구 분석 서비스를 사용할 수 없습니다. 나중에 다시 시도해주세요."
            )

        logging.info(f"Starting eye analysis for pet {pet_id}")
        
        try:
            # Download image for analysis
            try:
                image_bytes = self.storage_service.download_as_bytes(file_path)
                logging.info(f"Image downloaded successfully for pet {pet_id}")
            except FileNotFoundError:
                logging.error(f"Image file not found in GCS for pet {pet_id}: {file_path}")
                return BiometricAnalysisResult(
                    success=False,
                    error_message="GCS에서 분석할 이미지를 찾을 수 없습니다."
                )
            except Exception as e:
                logging.error(f"Failed to download image for pet {pet_id}: {e}")
                return BiometricAnalysisResult(
                    success=False,
                    error_message=f"이미지 다운로드 중 오류가 발생했습니다: {str(e)}"
                )

            # Run eye analysis
            try:
                logging.info(f"Running eye analysis prediction for pet {pet_id}")
                disease_name, probability, all_predictions = self.eye_analyzer.predict(image_bytes)
                logging.info(f"Eye analysis completed for pet {pet_id}. Disease: {disease_name}, Probability: {probability}")
            except Exception as e:
                logging.error(f"Eye analysis prediction failed for pet {pet_id}: {e}")
                return BiometricAnalysisResult(
                    success=False,
                    error_message=f"안구 분석 중 오류가 발생했습니다: {str(e)}"
                )

            # Make image public (non-critical operation)
            try:
                image_url = self.storage_service.make_public_and_get_url(file_path)
                logging.info(f"Image made public for pet {pet_id}")
            except Exception as e:
                logging.error(f"Failed to make image public for pet {pet_id}: {e}")
                image_url = None

            # Prepare result data
            result_data = {
                'pet_id': pet_id,
                'analysis_type': 'eye',
                'image_url': image_url,
                'result': {'final_disease_name': disease_name, 'probability': probability},
                'raw_predictions': all_predictions
            }
            
            # Save analysis result (non-critical operation)
            analysis_id = None
            try:
                analysis_id = save_analysis_result('analysis_history', user_id, result_data)
                logging.info(f"Analysis result saved with ID {analysis_id} for pet {pet_id}")
            except Exception as e:
                logging.error(f"Failed to save analysis result for pet {pet_id}: {e}")
            
            return BiometricAnalysisResult(
                success=True,
                confidence=probability,
                features={
                    'disease_name': disease_name,
                    'probability': probability,
                    'image_url': image_url
                },
                analysis_id=analysis_id,
                metadata={'raw_predictions': all_predictions}
            )
            
        except Exception as e:
            logging.error(f"Eye analysis failed for pet {pet_id}: {e}", exc_info=True)
            return BiometricAnalysisResult(
                success=False,
                error_message=f"안구 분석 중 예상치 못한 오류가 발생했습니다: {str(e)}"
            )

    # ============= Batch Processing (Future Enhancement) =============

    def schedule_analysis(self, pet_id: str, analysis_type: str, file_path: str) -> str:
        """Schedule biometric analysis for asynchronous processing.
        
        Args:
            pet_id: The pet's unique identifier
            analysis_type: Type of analysis ('nose' or 'eye')
            file_path: Storage path of the image
            
        Returns:
            Task ID for tracking analysis progress
            
        Note:
            This is a placeholder for future asynchronous processing implementation.
        """
        # TODO: Implement actual background task scheduling
        task_id = f"{analysis_type}_{pet_id}_{file_path.split('/')[-1]}"
        logging.info(f"Scheduled {analysis_type} analysis for pet {pet_id}, task ID: {task_id}")
        return task_id

    def get_analysis_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of scheduled analysis task.
        
        Args:
            task_id: Task identifier returned by schedule_analysis
            
        Returns:
            Task status information
            
        Note:
            This is a placeholder for future asynchronous processing implementation.
        """
        # TODO: Implement actual task status tracking
        return {
            'task_id': task_id,
            'status': 'pending',
            'message': 'Asynchronous processing not yet implemented'
        }
