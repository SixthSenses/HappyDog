# app/api/pets/services.py
import logging
import uuid
from typing import Dict, Any, Optional
from dataclasses import asdict
from firebase_admin import firestore

# 도메인 모델
from app.models.pet import Pet, PetGender

# 유틸리티 및 타 도메인 서비스
from app.utils.datetime_utils import DateTimeUtils
from app.api.pet_care.settings.services import PetCareSettingService
from app.services.storage_service import StorageService
from app.services.firestore_service import save_analysis_result

# ML 파이프라인
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline
from eyes_models.eyes_lib.inference import EyeAnalyzer


class PetService:
    """
    반려동물의 고유 식별 정보(프로필, 생체인식) 관리를 전담하는 서비스.
    """
    def __init__(self,
                 pet_care_setting_service: PetCareSettingService,
                 storage_service: StorageService,
                 nose_pipeline: NosePrintPipeline,
                 eye_analyzer: EyeAnalyzer):
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')
        # 의존성 주입 (Dependency Injection)
        self.pet_care_setting_service = pet_care_setting_service
        self.storage_service = storage_service
        self.nose_pipeline = nose_pipeline
        self.eye_analyzer = eye_analyzer
        logging.info("PetService initialized with dependencies.")

    def get_pet_by_id_and_owner(self, pet_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """pet_id로 반려동물을 찾되, user_id가 소유주일 경우에만 반환합니다."""
        doc = self.pets_ref.document(pet_id).get()
        if doc.exists and doc.to_dict().get('user_id') == user_id:
            return doc.to_dict()
        return None
        
    def register_pet(self, user_id: str, pet_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        [트랜잭션] 최초 반려동물 등록 및 펫케어 초기 설정 생성을 원자적으로 처리합니다.
        """
        transaction = self.db.transaction()
        pet_id = str(uuid.uuid4())
        pet_ref = self.pets_ref.document(pet_id)

        @firestore.transactional
        def _register_in_transaction(transaction):
            # 1. pets 컬렉션에 프로필 문서 생성
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
            
            pet_dict = asdict(new_pet)
            pet_dict['gender'] = new_pet.gender.value
            firestore_data = DateTimeUtils.for_firestore(pet_dict)
            
            transaction.set(pet_ref, firestore_data)
            logging.info(f"Transaction: Pet profile created for {pet_id}")

            # 2. [도메인 간 상호작용] pet_care.settings 서비스 호출
            # 트랜잭션 내에서 외부 서비스 호출은 주의가 필요하지만,
            # create_initial_settings가 멱등성을 가지거나 실패 시 롤백된다면 가능합니다.
            self.pet_care_setting_service.create_initial_settings_transactional(
                transaction, # 트랜잭션을 전달하여 원자성 보장
                pet_id=pet_id,
                gender=new_pet.gender.value,
                breed=new_pet.breed,
                current_weight=new_pet.initial_weight
            )
            logging.info(f"Transaction: Pet care settings creation requested for {pet_id}")
            return firestore_data

        try:
            created_pet_data = _register_in_transaction(transaction)
            return created_pet_data
        except Exception as e:
            logging.error(f"Pet registration transaction failed for user {user_id}: {e}", exc_info=True)
            raise RuntimeError("반려동물 등록 및 설정 생성에 실패했습니다. 다시 시도해주세요.")

    def register_nose_print_for_pet(self, pet_id: str, user_id: str, file_path: str) -> Dict[str, Any]:
        """비문 분석 및 등록/인증 로직."""
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("비문을 등록할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        if pet_info.get('is_verified', False):
            return {"status": "ALREADY_VERIFIED", "message": "이미 비문 인증이 완료된 반려동물입니다."}
        
        result = self.nose_pipeline.process_image(self.storage_service, file_path)
        status = result.get("status")

        if status == "SUCCESS":
            public_url = self.storage_service.make_public_and_get_url(file_path)
            update_data = {
                "is_verified": True,
                "nose_print_url": public_url,
                "faiss_id": result['faiss_id']
            }
            self.pets_ref.document(pet_id).update(update_data)
            self.nose_pipeline.add_vector_to_index(result['vector']) # DB 업데이트 성공 후 인덱스에 영구 반영
            return {"status": "SUCCESS", "message": "비문이 성공적으로 등록 및 인증되었습니다."}
        
        return result # DUPLICATE, INVALID_IMAGE, ERROR 상태 그대로 반환

    def analyze_eye_image_for_pet(self, user_id: str, pet_id: str, file_path: str) -> Dict[str, Any]:
        """안구 이미지 분석 로직."""
        if not self.get_pet_by_id_and_owner(pet_id, user_id):
            raise PermissionError("안구 분석을 요청할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        try:
            image_bytes = self.storage_service.download_as_bytes(file_path)
        except FileNotFoundError:
            raise RuntimeError("GCS에서 분석할 이미지를 찾을 수 없습니다.")

        disease_name, probability, all_predictions = self.eye_analyzer.predict(image_bytes)
        image_url = self.storage_service.make_public_and_get_url(file_path)

        result_data = {
            'pet_id': pet_id,
            'analysis_type': 'eye',
            'image_url': image_url,
            'result': {'final_disease_name': disease_name, 'probability': probability},
            'raw_predictions': all_predictions
        }
        
        analysis_id = save_analysis_result('analysis_history', user_id, result_data)
        
        return {'analysis_id': analysis_id, 'disease_name': disease_name, 'probability': probability}