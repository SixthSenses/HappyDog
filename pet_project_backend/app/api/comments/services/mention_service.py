# app/api/comments/services/mention_service.py
"""
댓글 멘션 처리를 담당하는 서비스
- 텍스트에서 멘션 추출 및 해석
- 사용자명 → user_id 변환
- 멘션 권한 검증
"""
import logging
from typing import List, Dict, Any
from firebase_admin import firestore

from app.utils.mentions import extract_mention_nicknames


class CommentMentionService:
    """
    댓글 멘션 추출 및 해석을 담당하는 서비스
    """
    def __init__(self):
        self.db = firestore.client()
        self.users_ref = self.db.collection('users')

    def extract_mentions(self, text: str) -> List[str]:
        """
        텍스트에서 '@닉네임' 형식의 멘션을 추출합니다.
        반환값: 중복 제거된 닉네임 리스트
        """
        if not text:
            return []
        return extract_mention_nicknames(text)

    def resolve_mentioned_users(self, usernames: List[str], sender_id: str) -> List[str]:
        """
        닉네임 리스트를 user_id 리스트로 변환합니다.
        - 존재하지 않는 닉네임은 제외
        - 자기 자신에 대한 멘션은 제외
        - 중복 제거 및 순서 보장
        """
        if not usernames:
            return []

        mentioned_user_ids: List[str] = []
        for nickname in usernames:
            try:
                query = self.users_ref.where('nickname', '==', nickname).limit(1).stream()
                user_doc = next(query, None)
                if user_doc and user_doc.id != sender_id:
                    mentioned_user_ids.append(user_doc.id)
            except Exception as e:
                logging.warning(f"닉네임 해석 실패 (nickname: {nickname}): {e}")
                continue

        # 중복 제거하면서 순서 보장 (dict.fromkeys 활용)
        return list(dict.fromkeys(mentioned_user_ids))

    def resolve_mentions_from_text(self, text: str, sender_id: str) -> Dict[str, Any]:
        """
        텍스트에서 멘션을 추출하고 user_id로 해석하는 전체 프로세스입니다.
        반환값: {
            'mentioned_nicknames': List[str],  # 추출된 닉네임들
            'mentioned_user_ids': List[str],   # 해석된 user_id들
            'resolved_count': int,             # 성공적으로 해석된 멘션 수
            'failed_nicknames': List[str]      # 해석에 실패한 닉네임들
        }
        """
        mentioned_nicknames = self.extract_mentions(text)
        if not mentioned_nicknames:
            return {
                'mentioned_nicknames': [],
                'mentioned_user_ids': [],
                'resolved_count': 0,
                'failed_nicknames': []
            }

        mentioned_user_ids = []
        failed_nicknames = []

        for nickname in mentioned_nicknames:
            try:
                query = self.users_ref.where('nickname', '==', nickname).limit(1).stream()
                user_doc = next(query, None)
                if user_doc and user_doc.id != sender_id:
                    mentioned_user_ids.append(user_doc.id)
                elif not user_doc:
                    failed_nicknames.append(nickname)
                # user_doc.id == sender_id인 경우는 조용히 무시 (자기 멘션)
            except Exception as e:
                logging.warning(f"닉네임 해석 실패 (nickname: {nickname}): {e}")
                failed_nicknames.append(nickname)

        # 중복 제거하면서 순서 보장
        mentioned_user_ids = list(dict.fromkeys(mentioned_user_ids))

        return {
            'mentioned_nicknames': mentioned_nicknames,
            'mentioned_user_ids': mentioned_user_ids,
            'resolved_count': len(mentioned_user_ids),
            'failed_nicknames': failed_nicknames
        }

    def validate_mention_permissions(self, sender_id: str, mentioned_user_ids: List[str]) -> List[str]:
        """
        멘션 권한을 검증합니다.
        현재는 모든 멘션을 허용하지만, 향후 블록 기능 등을 추가할 수 있습니다.
        반환값: 실제로 멘션 가능한 user_id 리스트
        """
        # 향후 확장 가능한 구조:
        # - 사용자 간 블록 관계 확인
        # - 프라이버시 설정 확인
        # - 멘션 허용/차단 설정 확인
        
        # 현재는 모든 유효한 멘션을 허용
        valid_mentions = []
        for user_id in mentioned_user_ids:
            if user_id != sender_id:  # 자기 자신 멘션 방지
                valid_mentions.append(user_id)
        
        return valid_mentions

    def get_mention_statistics(self, comment_id: str) -> Dict[str, int]:
        """
        특정 댓글의 멘션 통계를 반환합니다.
        디버깅이나 분석 목적으로 사용할 수 있습니다.
        """
        # 향후 멘션 통계가 필요한 경우 구현
        return {
            'total_mentions': 0,
            'valid_mentions': 0,
            'failed_mentions': 0
        }
