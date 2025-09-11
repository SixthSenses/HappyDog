# app/api/users/services/stats_service.py
import logging
from typing import Optional, Dict, Any
from firebase_admin import firestore


class UserStatsService:
    """
    사용자 통계 정보 관리 서비스 클래스.
    게시물 수, 활동 지표 등의 집계 데이터를 처리합니다.
    PostService에 의존하지 않고 직접 Firestore 쿼리를 사용합니다.
    """
    
    def __init__(self):
        """서비스 초기화"""
        self.db = firestore.client()
        self.posts_ref = self.db.collection('posts')
        self.users_ref = self.db.collection('users')
        
    def init_app(self, app):
        """Flask 앱 초기화"""
        self.app = app
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        사용자의 통계 정보를 조회합니다.
        :param user_id: 통계를 조회할 사용자 ID
        :return: 사용자 통계 딕셔너리
        """
        try:
            stats = {}
            
            # 게시물 수 직접 조회 (PostService 의존성 제거)
            post_count = self._count_posts_by_user_id(user_id)
            stats['post_count'] = post_count
            
            # 향후 다른 통계 정보 추가 가능
            # stats['follower_count'] = self._count_followers(user_id)
            # stats['following_count'] = self._count_following(user_id)
            
            return stats
        except Exception as e:
            logging.error(f"사용자 통계 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise
    
    def _count_posts_by_user_id(self, author_id: str) -> int:
        """
        특정 사용자가 작성한 게시물의 총 개수를 반환합니다.
        PostService의 count_posts_by_user_id와 동일한 로직을 직접 구현합니다.
        """
        try:
            query = self.posts_ref.where('author.user_id', '==', author_id)
            count_query = query.count()
            count_result = count_query.get()
            return count_result[0][0].value
        except Exception as e:
            logging.error(f"사용자 게시물 수 집계 실패 (author_id: {author_id}): {e}", exc_info=True)
            return 0
    
    def update_post_count_cache(self, user_id: str, delta: int) -> None:
        """
        게시물 수 변경을 캐시에 반영합니다.
        향후 이벤트 기반 업데이트를 위한 인터페이스입니다.
        :param user_id: 사용자 ID
        :param delta: 변경량 (+1 for creation, -1 for deletion)
        """
        try:
            # 현재는 실시간 계산을 사용하지만, 향후 캐시 구현 가능
            # 예: Redis나 Firestore의 별도 통계 컬렉션 업데이트
            logging.info(f"게시물 수 변경 이벤트 (user_id: {user_id}, delta: {delta})")
            pass
        except Exception as e:
            logging.error(f"게시물 수 캐시 업데이트 실패 (user_id: {user_id}): {e}", exc_info=True)
            # 캐시 업데이트 실패는 치명적이지 않으므로 예외를 다시 발생시키지 않음
            pass
