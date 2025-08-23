# app/api/breeds/services.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from firebase_admin import firestore
from flask import current_app

logger = logging.getLogger(__name__)

class BreedService:
    """
    강아지 품종 관련 비즈니스 로직을 처리하는 서비스 클래스
    """
    
    def __init__(self):
        self.db = firestore.client()
        self.breeds_collection = self.db.collection('breeds')
    
    def get_all_breeds(self, limit: Optional[int] = None, offset: int = 0) -> Tuple[List[Dict[str, Any]], int]:
        """
        모든 품종 목록을 조회합니다.
        
        Args:
            limit: 조회할 최대 개수 (None이면 모든 데이터)
            offset: 건너뛸 개수 (페이지네이션용)
            
        Returns:
            Tuple[품종 목록, 전체 개수]
        """
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
        try:
            query = self.breeds_collection.order_by('breed_name')
            
            if limit:
                query = query.limit(limit)
            
            docs = query.stream()
            breeds_summary = []
            
            for doc in docs:
                breed_data = doc.to_dict()
                summary = {
                    'breed_name': doc.id,
                    'life_expectancy': breed_data.get('life_expectancy')
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
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        품종 데이터베이스 통계 정보를 조회합니다.
        
        Returns:
            통계 정보 딕셔너리
        """
        try:
            all_breeds, total_count = self.get_all_breeds()
            
            if not all_breeds:
                return {
                    'total_breeds': 0,
                    'avg_life_expectancy': 0,
                    'min_life_expectancy': 0,
                    'max_life_expectancy': 0
                }
            
            life_expectancies = [breed['life_expectancy'] for breed in all_breeds if breed.get('life_expectancy')]
            
            stats = {
                'total_breeds': total_count,
                'avg_life_expectancy': sum(life_expectancies) / len(life_expectancies) if life_expectancies else 0,
                'min_life_expectancy': min(life_expectancies) if life_expectancies else 0,
                'max_life_expectancy': max(life_expectancies) if life_expectancies else 0
            }
            
            logger.info(f"품종 통계 정보 조회 완료: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"품종 통계 정보 조회 실패: {e}")
            raise
