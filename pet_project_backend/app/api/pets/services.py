# app/api/pets/services.py
import logging
import uuid
from typing import Dict, Any, Optional
from dataclasses import asdict
from firebase_admin import firestore
from firebase_admin.firestore import Transaction

# 도메인 모델
from app.models.pet import Pet, PetGender

# 유틸리티 및 타 도메인/공용 서비스
from app.utils.datetime_utils import DateTimeUtils
from app.api.pet_care.settings.services import PetCareSettingService
from app.services.storage_service import StorageService
from app.services.firestore_service import save_analysis_result

# ML 파이프라인
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline
from eyes_models.eyes_lib.inference import EyeAnalyzer

class PetService:
    """반려동물의 고유 식별 정보(프로필, 생체인식) 관리를 전담하는 서비스."""
    def __init__(self,
                 pet_care_setting_service: PetCareSettingService,
                 storage_service: StorageService,
                 nose_pipeline: NosePrintPipeline,
                 eye_analyzer: EyeAnalyzer):
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')
        self.pet_care_setting_service = pet_care_setting_service
        self.storage_service = storage_service
        self.nose_pipeline = nose_pipeline
        self.eye_analyzer = eye_analyzer
        logging.info("PetService initialized with dependencies.")

    def get_pet_by_id_and_owner(self, pet_id: str, user_id: str) -> Optional[Pet]:
        """
        반려동물 정보를 가져와 Pet 객체로 변환하여 반환합니다.
        """
        doc = self.pets_ref.document(pet_id).get()
        if doc.exists:
            pet_data = doc.to_dict()
            if pet_data.get('user_id') == user_id:
                # 딕셔너리 대신, 이제 신뢰할 수 있는 Pet 객체를 반환합니다.
                return Pet.from_dict(pet_data)
        return None

    def get_pet_profile(self, pet_id: str, user_id: str) -> Pet:
        """[소유자 전용] 반려동물 프로필 정보를 조회합니다."""
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("프로필을 조회할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        return pet_info

    def get_pet_profile_dict(self, pet_id: str, user_id: str) -> Dict[str, Any]:
        """[소유자 전용] 반려동물 프로필 정보를 딕셔너리 형태로 조회합니다."""
        pet = self.get_pet_profile(pet_id, user_id)
        return self._pet_to_dict(pet)

    def get_public_pet_profile(self, pet_id: str) -> Dict[str, Any]:
        """[공개용] 소유권 검사 없이 반려동물의 공개 프로필 정보를 조회합니다."""
        doc = self.pets_ref.document(pet_id).get()
        if not doc.exists:
            raise FileNotFoundError("해당 ID의 반려동물을 찾을 수 없습니다.")
        return doc.to_dict()

    def _pet_to_dict(self, pet: Pet) -> Dict[str, Any]:
        """Pet 객체를 딕셔너리로 변환합니다."""
        pet_dict = asdict(pet)
        pet_dict['gender'] = pet.gender.value
        return pet_dict

    def register_pet(self, user_id: str, pet_data: Dict[str, Any]) -> Pet:
        """[트랜잭션] 최초 반려동물 등록 및 펫케어 초기 설정 생성을 원자적으로 처리합니다."""
        transaction = self.db.transaction()
        pet_id = str(uuid.uuid4())
        pet_ref = self.pets_ref.document(pet_id)

        @firestore.transactional
        def _register_in_transaction(transaction: Transaction):
            new_pet = Pet(
                pet_id=pet_id, user_id=user_id,
                name=pet_data['name'], gender=PetGender(pet_data['gender']),
                breed=pet_data['breed'], birthdate=pet_data['birthdate'],
                initial_weight=pet_data['current_weight'],
                fur_color=pet_data.get('fur_color'),
                health_concerns=pet_data.get('health_concerns', [])
            )
            pet_dict = asdict(new_pet)
            pet_dict['gender'] = new_pet.gender.value
            firestore_data = DateTimeUtils.for_firestore(pet_dict)
            transaction.set(pet_ref, firestore_data)
            
            self.pet_care_setting_service.create_initial_settings_transactional(
                transaction, pet_id=pet_id, gender=new_pet.gender.value,
                breed=new_pet.breed, current_weight=new_pet.initial_weight
            )
            return new_pet

        try:
            return _register_in_transaction(transaction)
        except Exception as e:
            logging.error(f"Pet registration transaction failed for user {user_id}: {e}", exc_info=True)
            raise RuntimeError("반려동물 등록 및 설정 생성에 실패했습니다. 다시 시도해주세요.")

    def update_pet_profile(self, pet_id: str, user_id: str, update_data: Dict[str, Any]) -> Pet:
        """반려동물 프로필 정보를 부분 업데이트합니다."""
        pet_ref = self.pets_ref.document(pet_id)
        doc = pet_ref.get()
        if not doc.exists or doc.to_dict().get('user_id') != user_id:
            raise PermissionError("프로필을 수정할 권한이 없거나 반려동물을 찾을 수 없습니다.")
        if not update_data:
            raise ValueError("수정할 데이터가 제공되지 않았습니다.")
            
        pet_ref.update(update_data)
        logging.info(f"Pet profile updated for {pet_id} with fields: {list(update_data.keys())}")
        
        # 업데이트된 Pet 객체를 반환
        updated_pet = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not updated_pet:
            raise RuntimeError("업데이트된 반려동물 정보를 조회할 수 없습니다.")
        return updated_pet

    def register_nose_print_for_pet(self, pet_id: str, user_id: str, file_path: str) -> Dict[str, Any]:
        """비문 분석 및 등록/인증 로직."""
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("비문을 등록할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        # Pet 객체의 속성에 직접 접근
        if pet_info.is_verified:
            logging.info(f"Pet {pet_id} is already verified. Skipping nose print registration.")
            return {"status": "ALREADY_VERIFIED", "message": "이미 비문 인증이 완료된 반려동물입니다."}
        
        logging.info(f"Starting nose print registration for pet {pet_id}")
        result = self.nose_pipeline.process_image(self.storage_service, file_path)
        status = result.get("status")

        if status == "SUCCESS":
            logging.info(f"Nose print processing successful for pet {pet_id}. Updating database...")
            
            # 트랜잭션으로 DB 업데이트와 인덱스 업데이트를 원자적으로 처리
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
                # DB 업데이트 성공 후 인덱스에 영구 반영
                self.nose_pipeline.add_vector_to_index(result['vector'])
                logging.info(f"Nose print registration completed successfully for pet {pet_id}")
                return {"status": "SUCCESS", "message": "비문이 성공적으로 등록 및 인증되었습니다."}
            except Exception as e:
                logging.error(f"Failed to update nose print data for pet {pet_id}: {e}")
                raise RuntimeError("비문 등록 중 데이터베이스 오류가 발생했습니다.")
        
        logging.warning(f"Nose print processing failed for pet {pet_id}. Status: {status}")
        return result # DUPLICATE, INVALID_IMAGE, ERROR 상태 그대로 반환

    def analyze_eye_image_for_pet(self, user_id: str, pet_id: str, file_path: str) -> Dict[str, Any]:
        """안구 이미지 분석 로직."""
        if not self.get_pet_by_id_and_owner(pet_id, user_id):
            raise PermissionError("안구 분석을 요청할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        logging.info(f"Starting eye analysis for pet {pet_id}")
        
        try:
            image_bytes = self.storage_service.download_as_bytes(file_path)
            logging.info(f"Image downloaded successfully for pet {pet_id}")
        except FileNotFoundError:
            logging.error(f"Image file not found in GCS for pet {pet_id}: {file_path}")
            raise RuntimeError("GCS에서 분석할 이미지를 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"Failed to download image for pet {pet_id}: {e}")
            raise RuntimeError(f"이미지 다운로드 중 오류가 발생했습니다: {str(e)}")

        try:
            logging.info(f"Running eye analysis prediction for pet {pet_id}")
            disease_name, probability, all_predictions = self.eye_analyzer.predict(image_bytes)
            logging.info(f"Eye analysis completed for pet {pet_id}. Disease: {disease_name}, Probability: {probability}")
        except Exception as e:
            logging.error(f"Eye analysis prediction failed for pet {pet_id}: {e}")
            raise RuntimeError(f"안구 분석 중 오류가 발생했습니다: {str(e)}")

        try:
            image_url = self.storage_service.make_public_and_get_url(file_path)
            logging.info(f"Image made public for pet {pet_id}")
        except Exception as e:
            logging.error(f"Failed to make image public for pet {pet_id}: {e}")
            # 이미지 공개 실패는 분석 결과에 영향을 주지 않으므로 경고만 기록
            image_url = None

        result_data = {
            'pet_id': pet_id,
            'analysis_type': 'eye',
            'image_url': image_url,
            'result': {'final_disease_name': disease_name, 'probability': probability},
            'raw_predictions': all_predictions
        }
        
        try:
            analysis_id = save_analysis_result('analysis_history', user_id, result_data)
            logging.info(f"Analysis result saved with ID {analysis_id} for pet {pet_id}")
        except Exception as e:
            logging.error(f"Failed to save analysis result for pet {pet_id}: {e}")
            # 분석 결과 저장 실패는 분석 자체의 성공을 막지 않음
            analysis_id = None
        
        return {'analysis_id': analysis_id, 'disease_name': disease_name, 'probability': probability}