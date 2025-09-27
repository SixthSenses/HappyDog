# app/api/breeds/services.py
import logging
from typing import List, Dict, Any, Optional, Tuple
import os
from flask import current_app

logger = logging.getLogger(__name__)

class BreedService:
    """
    강아지 품종 관련 비즈니스 로직을 처리하는 서비스 클래스
    """
    
    def __init__(self, db_client=None, storage_service=None, guide_blob_path: Optional[str] = None):
        self.db = db_client
        self.breeds_collection = self.db.collection('breeds') if self.db else None
        self.storage = storage_service
        # Path in Firebase Storage for the encyclopedia JSON (blob path, not URL)
        # Default: static/breeds/dog_guide.json (can override via env BREED_GUIDE_BLOB_PATH)
        self.guide_blob_path = guide_blob_path or os.getenv('BREED_GUIDE_BLOB_PATH') or 'static/breeds/dog_guide.json'
        if self.db is None:
            logger.info("BreedService initialized without Firestore client (docs mode or disabled persistence)")
        # Lazy caches for local JSON resources
        self._guide_map = None  # type: Optional[Dict[str, Dict[str, Any]]]
        self._guide_loaded = False
    
    def get_all_breeds(self, limit: Optional[int] = None, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        모든 품종 목록을 조회합니다.
        
        Args:
            limit: 조회할 최대 개수 (None이면 모든 데이터)
            offset: 건너뛸 개수 (페이지네이션용)
            
        Returns:
            Tuple[품종 목록, 전체 개수]
        """
        if self.breeds_collection is None:
            return [], 0
        try:
            # 전체 개수 조회
            all_docs = self.breeds_collection.stream()
            total_count = sum(1 for _ in all_docs)
            
            # 페이지네이션 적용하여 데이터 조회
            query = self.breeds_collection.order_by('breed_name')
            
            if offset > 0:
                # Firestore에서는 offset을 위해 limit + skip을 사용
                skip_docs = list(query.limit(offset).stream())
                if len(skip_docs) == offset:
                    last_doc = skip_docs[-1]
                    query = query.start_after(last_doc)
                else:
                    # offset이 전체 데이터 수보다 큰 경우
                    return [], total_count
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            breeds = []
            
            for doc in docs:
                breed_data = doc.to_dict()
                breed_data['breed_name'] = doc.id  # 문서 ID를 breed_name으로 설정
                breeds.append(breed_data)
            
            logger.info(f"품종 목록 조회 완료: {len(breeds)}개 (전체 {total_count}개)")
            return breeds, total_count
            
        except Exception as e:
            logger.error(f"품종 목록 조회 실패: {e}")
            raise
    
    def get_breed_by_name(self, breed_name: str) -> Optional[Dict[str, Any]]:
        """
        특정 품종 정보를 조회합니다.
        
        Args:
            breed_name: 품종명
            
        Returns:
            품종 정보 딕셔너리 또는 None
        """
        if self.breeds_collection is None:
            return None
        try:
            doc_ref = self.breeds_collection.document(breed_name)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.warning(f"품종을 찾을 수 없음: {breed_name}")
                return None
            
            breed_data = doc.to_dict()
            breed_data['breed_name'] = doc.id
            
            logger.info(f"품종 정보 조회 완료: {breed_name}")
            return breed_data
            
        except Exception as e:
            logger.error(f"품종 정보 조회 실패 ({breed_name}): {e}")
            raise
    
    def search_breeds(self, query: str, limit: int = 50, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        품종명으로 검색합니다.
        
        Args:
            query: 검색 쿼리
            limit: 조회할 최대 개수
            offset: 건너뛸 개수
            
        Returns:
            Tuple[검색 결과 목록, 전체 검색 결과 개수]
        """
        if self.breeds_collection is None:
            return [], 0
        try:
            # Firestore에서는 부분 문자열 검색이 제한적이므로
            # 모든 데이터를 가져와서 클라이언트 측에서 필터링
            all_breeds, _ = self.get_all_breeds()
            
            # 검색 쿼리로 필터링 (대소문자 구분 없이)
            query_lower = query.lower()
            filtered_breeds = [
                breed for breed in all_breeds
                if query_lower in breed['breed_name'].lower()
            ]
            
            total_count = len(filtered_breeds)
            
            # 페이지네이션 적용
            end_index = offset + limit
            paginated_breeds = filtered_breeds[offset:end_index]
            
            logger.info(f"품종 검색 완료: '{query}' -> {len(paginated_breeds)}개 (전체 {total_count}개)")
            return paginated_breeds, total_count
            
        except Exception as e:
            logger.error(f"품종 검색 실패 ('{query}'): {e}")
            raise
    
    def get_breeds_summary(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        품종 요약 정보를 조회합니다. (드롭다운 등에서 사용)
        
        Args:
            limit: 조회할 최대 개수
            
        Returns:
            품종 요약 정보 목록
        """
        if self.breeds_collection is None:
            return []
        try:
            query = self.breeds_collection.order_by('breed_name')
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            breeds_summary = []
            
            for doc in docs:
                # Only minimal fields for dropdown selection at pet registration
                summary = {
                    'breed_name': doc.id
                }
                breeds_summary.append(summary)
            
            logger.info(f"품종 요약 정보 조회 완료: {len(breeds_summary)}개")
            return breeds_summary
            
        except Exception as e:
            logger.error(f"품종 요약 정보 조회 실패: {e}")
            raise
    
    def breed_exists(self, breed_name: str) -> bool:
        """
        특정 품종이 존재하는지 확인합니다.
        
        Args:
            breed_name: 품종명
            
        Returns:
            존재 여부
        """
        if self.breeds_collection is None:
            return False
        try:
            doc_ref = self.breeds_collection.document(breed_name)
            doc = doc_ref.get()
            return doc.exists
            
        except Exception as e:
            logger.error(f"품종 존재 여부 확인 실패 ({breed_name}): {e}")
            return False
    
    def get_breed_ideal_weight(self, breed_name: str, gender: str) -> Optional[float]:
        """
        특정 품종의 이상적인 체중을 조회합니다. (펫케어 권장량 계산용)
        
        Args:
            breed_name: 품종명
            gender: 성별 ('MALE' 또는 'FEMALE')
            
        Returns:
            이상적인 체중(kg) 또는 None
        """
        if self.breeds_collection is None:
            return None
        try:
            breed_data = self.get_breed_by_name(breed_name)
            if not breed_data:
                return None
            
            weight_data = breed_data.get('weight_kg', {})
            gender_key = gender.lower()
            
            if gender_key in weight_data:
                ideal_weight = weight_data[gender_key]
                logger.info(f"품종 '{breed_name}' {gender} 이상 체중: {ideal_weight}kg")
                return ideal_weight
            else:
                logger.warning(f"품종 '{breed_name}'에 {gender} 체중 정보 없음")
                return None
                
        except Exception as e:
            logger.error(f"품종 이상 체중 조회 실패 ({breed_name}, {gender}): {e}")
            return None
    
    # 통계 관련 기능은 폐지됨 (UI 정책에 따라 모든 요약/통계 제거)

    # ===============================
    # Encyclopedia (dog_guide.json)
    # ===============================
    def _load_guides(self) -> None:
        """Load and normalize dog_guide.json into an internal map keyed by breed_name (Korean).

        This reads from pet_project_backend/scripts/breed_info/dog_guide.json.
        Fields are normalized to an English-keyed structure for consistent API output.
        """
        if self._guide_loaded:
            return
        try:
            import json

            raw: Dict[str, Any] = {}

            # 1) Try Firebase Storage if available
            if self.storage is not None and getattr(self.storage, 'bucket', None) is not None and self.guide_blob_path:
                try:
                    data = self.storage.download_as_bytes(self.guide_blob_path)
                    raw = json.loads(data.decode('utf-8'))
                    logger.info(f"Loaded breed guides from Firebase Storage blob: {self.guide_blob_path}")
                except Exception as se:
                    logger.warning(f"Failed to load guide from storage (will fallback to local): {se}")

            # 2) Fallback to local file within repo if storage not available or failed
            if not raw:
                here = os.path.dirname(__file__)
                guide_path = os.path.abspath(os.path.join(here, '../../../scripts/breed_info/dog_guide.json'))
                if os.path.exists(guide_path):
                    with open(guide_path, 'r', encoding='utf-8') as f:
                        raw = json.load(f)
                    logger.info(f"Loaded breed guides from local file: {guide_path}")
                else:
                    logger.warning(f"dog_guide.json not found locally at {guide_path}")
                    self._guide_map = {}
                    self._guide_loaded = True
                    return

            def norm_item(k: str, v: Dict[str, Any]) -> Dict[str, Any]:
                # Korean keys mapping -> English keys used in schema
                eng_name = v.get('영문명')
                base = v.get('기본 정보') or {}
                perso = v.get('성격 특징') or {}
                diseases = v.get('주요 질환') or []
                care = v.get('케어 포인트') or []
                return {
                    'breed_name': k,
                    'english_name': eng_name,
                    'basic_info': {
                        'weight': base.get('체중'),
                        'height': base.get('체고'),
                        'life_span': base.get('수명'),
                        'origin': base.get('원산지'),
                    },
                    'personality': {
                        'strengths': perso.get('장점'),
                        'weaknesses': perso.get('단점'),
                        'traits': perso.get('특성'),
                    },
                    'common_diseases': diseases,
                    'care_points': care,
                }

            self._guide_map = {breed_k: norm_item(breed_k, breed_v) for breed_k, breed_v in raw.items()}
            self._guide_loaded = True
            logger.info(f"Loaded breed guides: {len(self._guide_map)} entries")
        except Exception as e:
            logger.error(f"Failed to load dog_guide.json: {e}")
            self._guide_map = {}
            self._guide_loaded = True

    def get_breed_guide(self, breed_name: str) -> Optional[Dict[str, Any]]:
        """Return encyclopedia content for the given breed name (Korean)."""
        self._load_guides()
        if not self._guide_map:
            return None
        # Exact match first
        guide = self._guide_map.get(breed_name)
        if guide:
            return guide
        # Fallback: case-insensitive match for safety (even though Korean is case-insensitive)
        name_lower = breed_name.lower()
        for k, v in self._guide_map.items():
            if k.lower() == name_lower:
                return v
        return None

    def search_breed_guides(self, query: str, limit: int = 20, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """Search encyclopedia entries by Korean breed name substring."""
        self._load_guides()
        if not self._guide_map:
            return [], 0
        q = (query or '').strip().lower()
        items = [v for k, v in self._guide_map.items() if q in k.lower()]
        total = len(items)
        return items[offset: offset + limit], total
