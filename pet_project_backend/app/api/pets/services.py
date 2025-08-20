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

        # 펫케어 설정 자동 생성 (온보딩 연동)
        care_settings = self._generate_care_settings(new_pet)
        pet_data_dict['care_settings'] = care_settings

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

    def _generate_care_settings(self, pet: Pet) -> Dict[str, Any]:
        """
        펫 정보를 바탕으로 펫케어 기본 설정을 생성합니다.
        
        Args:
            pet: Pet 객체
            
        Returns:
            펫케어 설정 딕셔너리
        """
        try:
            # 나이 계산 (월 단위)
            if pet.birthdate:
                if isinstance(pet.birthdate, date):
                    birthdate = pet.birthdate
                else:
                    # datetime 객체인 경우 date로 변환
                    birthdate = pet.birthdate.date()
                
                today = date.today()
                age_months = (today.year - birthdate.year) * 12 + (today.month - birthdate.month)
                age_months = max(0, age_months)
            else:
                age_months = 12  # 기본값: 1세
            
            # 품종별 이상 체중 조회
            ideal_weight = 15.0  # 기본값
            if self.breed_service and pet.breed:
                breed_weight = self.breed_service.get_breed_ideal_weight(pet.breed, pet.gender.value)
                if breed_weight:
                    ideal_weight = breed_weight
            
            # 현재 체중이 있으면 사용, 없으면 이상 체중 사용
            current_weight = pet.current_weight or ideal_weight
            
            # RER 계산 (휴식대사율)
            rer_calories = 70 * (ideal_weight ** 0.75)
            
            # MER 승수 계산
            multiplier = self._calculate_mer_multiplier(pet, age_months)
            mer_calories = rer_calories * multiplier
            
            # 권장 음수량 계산
            recommended_water_ml = self._calculate_water_intake(mer_calories, pet.diet_type)
            
            # 빠른 증감을 위한 기본 증분 설정
            food_increment = max(25, round(mer_calories * 0.05))  # MER의 5% 또는 최소 25kcal
            water_increment = max(50, round(recommended_water_ml * 0.1))  # 권장량의 10% 또는 최소 50ml
            activity_increment = 15 if age_months < 12 else 30  # 자견은 15분, 성견은 30분
            
            care_settings = {
                'food_increment': food_increment,
                'water_increment': water_increment,
                'activity_increment': activity_increment,
                'recommended_calories': round(mer_calories, 1),
                'recommended_water_ml': round(recommended_water_ml, 1),
                'ideal_weight_kg': ideal_weight,
                'age_months': age_months,
                'mer_multiplier': multiplier,
                'generated_at': datetime.utcnow()
            }
            
            logging.info(f"펫케어 설정 생성 완료: {pet.pet_id} - 칼로리: {mer_calories}, 물: {recommended_water_ml}ml")
            return care_settings
            
        except Exception as e:
            logging.error(f"펫케어 설정 생성 실패 ({pet.pet_id}): {e}")
            # 기본값 반환
            return {
                'food_increment': 50,
                'water_increment': 100,
                'activity_increment': 30,
                'recommended_calories': 400.0,
                'recommended_water_ml': 400.0,
                'ideal_weight_kg': 15.0,
                'age_months': 12,
                'mer_multiplier': 1.6,
                'generated_at': datetime.utcnow()
            }
    
    def _calculate_mer_multiplier(self, pet: Pet, age_months: int) -> float:
        """MER 승수를 계산합니다."""
        # 생애 주기 확인
        if age_months < 4:
            return 3.0  # 자견 (4개월 미만)
        elif age_months < 12:
            return 2.0  # 자견 (4개월 이상)
        
        # 성견의 경우
        # 활동 수준에 따른 승수 (우선순위 높음)
        if pet.activity_level:
            if pet.activity_level == ActivityLevel.INACTIVE:
                return 1.4  # 비활동적 / 비만 경향
            elif pet.activity_level == ActivityLevel.LIGHT:
                return 2.0  # 가벼운 활동
            elif pet.activity_level == ActivityLevel.MODERATE:
                return 3.0  # 중간 수준 활동
            elif pet.activity_level in [ActivityLevel.ACTIVE, ActivityLevel.VERY_ACTIVE]:
                return 6.0  # 격렬한 활동 (워킹독)
        
        # 중성화 상태에 따른 기본 승수
        if pet.is_neutered is True:
            return 1.6  # 중성화한 성견
        elif pet.is_neutered is False:
            return 1.8  # 중성화하지 않은 성견
        else:
            return 1.6  # 기본값
    
    def _calculate_water_intake(self, mer_calories: float, diet_type: Optional[DietType]) -> float:
        """권장 음수량을 계산합니다."""
        base_water_ml = mer_calories
        
        # 식단 타입에 따른 조정
        if diet_type == DietType.WET_FOOD:
            return base_water_ml * 0.4  # 습식사료는 수분 함량이 높음
        elif diet_type == DietType.MIXED:
            return base_water_ml * 0.7  # 혼합식
        else:
            return base_water_ml  # 건사료 또는 기타

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
pet_service: Optional[PetService] = None