# app/api/pets/services.py
import logging
from firebase_admin import firestore
from typing import Optional, Dict, Any
from dataclasses import asdict
from datetime import date, datetime

from app.models.pet import Pet, ActivityLevel, DietType
from app.services.storage_service import StorageService
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline
from eyes_models.eyes_lib.inference import EyeAnalyzer
from app.services.firestore_service import save_analysis_result

class PetService:
    """
    반려동물 관련 비즈니스 로직을 담당하는 서비스 클래스.
    """
    def __init__(self, storage_service: StorageService, nose_pipeline: NosePrintPipeline, eye_analyzer: EyeAnalyzer, breed_service=None):
        """
        서비스 초기화 시 의존성 주입을 통해 필요한 서비스를 받습니다.
        """
        self.db = firestore.client()
        self.pets_ref = self.db.collection('pets')
        self.storage_service = storage_service
        self.nose_pipeline = nose_pipeline
        self.eye_analyzer = eye_analyzer
        self.breed_service = breed_service

    def get_pet_by_user_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """user_id로 반려동물 문서를 찾아 딕셔너리로 반환합니다."""
        query = self.pets_ref.where('user_id', '==', user_id).limit(1).stream()
        pet_doc = next(query, None)
        if pet_doc:
            pet_data = pet_doc.to_dict()
            pet_data['pet_id'] = pet_doc.id # 문서 ID를 포함하여 반환
            return pet_data
        return None

    def get_pet_by_id_and_owner(self, pet_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """pet_id로 반려동물을 찾되, user_id가 소유주일 경우에만 반환합니다."""
        try:
            doc = self.pets_ref.document(pet_id).get()
            if doc.exists and doc.to_dict().get('user_id') == user_id:
                pet_data = doc.to_dict()
                pet_data['pet_id'] = doc.id
                return pet_data
            return None
        except Exception as e:
            logging.error(f"ID와 소유주로 반려동물 조회 실패: {e}", exc_info=True)
            raise

    def create_pet(self, new_pet: Pet) -> Dict[str, Any]:
        """새로운 반려동물 정보를 Firestore에 저장합니다."""
        # 품종 유효성 검사
        if self.breed_service and not self.breed_service.breed_exists(new_pet.breed):
            raise ValueError(f"존재하지 않는 품종입니다: {new_pet.breed}")
        
        pet_data_dict = asdict(new_pet)
        pet_data_dict['gender'] = new_pet.gender.value
        
        # Enum 값들을 문자열로 변환
        if new_pet.activity_level:
            pet_data_dict['activity_level'] = new_pet.activity_level.value
        if new_pet.diet_type:
            pet_data_dict['diet_type'] = new_pet.diet_type.value
        
        # --- 수정된 부분: datetime.date 객체를 datetime.datetime으로 변환 ---
        if 'birthdate' in pet_data_dict and isinstance(pet_data_dict['birthdate'], date):
            bdate = pet_data_dict['birthdate']
            pet_data_dict['birthdate'] = datetime(bdate.year, bdate.month, bdate.day)
        # ----------------------------------------------------------------

        self.pets_ref.document(new_pet.pet_id).set(pet_data_dict)
        logging.info(f"새 반려동물 등록 완료: {new_pet.pet_id}, 품종: {new_pet.breed}")
        return pet_data_dict

    def update_pet(self, pet_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """기존 반려동물 정보를 업데이트합니다."""
        
        # --- 수정된 부분: datetime.date 객체를 datetime.datetime으로 변환 ---
        if 'birthdate' in update_data and isinstance(update_data['birthdate'], date):
            bdate = update_data['birthdate']
            update_data['birthdate'] = datetime(bdate.year, bdate.month, bdate.day)
        # ----------------------------------------------------------------

        pet_ref = self.pets_ref.document(pet_id)
        pet_ref.update(update_data)
        updated_doc = pet_ref.get()
        if updated_doc.exists:
            return updated_doc.to_dict()
        return None

    def register_nose_print_for_pet(self, pet_id: str, user_id: str, file_path: str) -> Dict[str, Any]:
        """
        특정 반려동물의 비문을 분석하고 등록/인증합니다.
        - routes 계층에서 전달받은 인자를 기반으로 소유권을 먼저 확인합니다.
        - ML 파이프라인의 모든 상태(SUCCESS, DUPLICATE 등)에 대한 명확한 응답을 반환합니다.
        """
        # 1. 소유권 확인
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("비문을 등록할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        # 2. 이미 인증되었는지 확인
        if pet_info.get('is_verified', False):
            return {"status": "ALREADY_VERIFIED", "message": "이미 비문 인증이 완료된 반려동물입니다."}
        
        # 3. ML 파이프라인 실행
        result = self.nose_pipeline.process_image(storage_service=self.storage_service, file_path=file_path)
        status = result.get("status")

        # 4. 파이프라인 결과에 따라 분기 처리
        if status == "SUCCESS":
            blob = self.storage_service.bucket.blob(file_path)
            blob.make_public()
            update_data = {
                "is_verified": True,
                "nose_print_url": blob.public_url,
                "faiss_id": result['faiss_id']
            }
            updated_pet = self.update_pet(pet_id, update_data)
            
            # DB 업데이트 성공 후 Faiss 인덱스에 벡터를 영구적으로 추가
            self.nose_pipeline.add_vector_to_index(result['vector'])
            
            return {"status": "SUCCESS", "message": "비문이 성공적으로 등록 및 인증되었습니다.", "pet": updated_pet}
        
        elif status == "DUPLICATE":
            return {
                "status": "DUPLICATE",
                "message": "이미 다른 반려동물의 비문으로 등록된 사진입니다."
            }
        
        elif status == "INVALID_IMAGE":
             return {"status": "INVALID_IMAGE", "message": "코를 명확하게 식별할 수 없습니다. 더 선명하거나 가까운 사진을 이용해주세요."}
        
        else: # "ERROR" 또는 예기치 않은 상태
            error_message = result.get("message", "비문 분석 중 알 수 없는 오류가 발생했습니다.")
            return {"status": "ERROR", "message": error_message}

    def analyze_eye_image_for_pet(self, user_id: str, pet_id: str, file_path: str) -> Dict[str, Any]:
        """
        GCS에 저장된 반려동물의 안구 이미지를 분석하고 결과를 Firestore에 저장합니다.
        - 소유권 확인 후 GCS에서 이미지를 다운로드하여 분석을 수행합니다.
        """
        # 1. 소유권 확인
        pet_info = self.get_pet_by_id_and_owner(pet_id, user_id)
        if not pet_info:
            raise PermissionError("안구 분석을 요청할 권한이 없거나 반려동물을 찾을 수 없습니다.")

        # 2. GCS에서 이미지 다운로드
        try:
            blob = self.storage_service.bucket.blob(file_path)
            if not blob.exists():
                raise RuntimeError("GCS에서 분석할 이미지를 찾을 수 없습니다.")
            image_bytes = blob.download_as_bytes()
        except Exception as e:
            logging.error(f"GCS 파일 다운로드 실패 (file_path: {file_path}): {e}")
            raise RuntimeError(f"스토리지에서 파일을 가져오는 데 실패했습니다.")

        # 3. EyeAnalyzer로 분석 실행
        final_disease_name, probability, all_predictions = self.eye_analyzer.predict(image_bytes)

        # 4. GCS 이미지 URL을 공개로 설정
        blob.make_public()
        image_url = blob.public_url

        # 5. Firestore에 저장할 데이터 구성
        result_data = {
            'pet_id': pet_id,
            'analysis_type': 'eye',
            'image_url': image_url,
            'result': {
                'final_disease_name': final_disease_name,
                'probability': probability
            },
            'raw_predictions': all_predictions
        }
        
        # 6. 분석 결과 저장 (공용 서비스 사용)
        analysis_id = save_analysis_result(
            collection_name='analysis_history', 
            user_id=user_id, 
            data=result_data
        )
        if not analysis_id:
            raise RuntimeError("분석 결과를 데이터베이스에 저장하는데 실패했습니다.")

        # 7. API 응답을 위한 최종 데이터 반환
        return {
            'analysis_id': analysis_id,
            'disease_name': final_disease_name,
            'probability': probability
        }

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
pet_service: Optional[PetService] = None