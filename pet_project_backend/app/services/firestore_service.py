# app/services/firestore_service.py
import datetime
import logging
from firebase_admin import firestore

from app.utils.datetime_utils import DateTimeUtils

def save_analysis_result(collection_name: str, user_id: str, data: dict) -> str:
    """
    AI 분석 결과를 Firestore의 지정된 컬렉션에 저장하고 문서 ID를 반환합니다.

    :param collection_name: 문서를 저장할 컬렉션 이름 (예: 'analysis_history')
    :param user_id: 분석을 요청한 사용자 ID
    :param data: 저장할 데이터 딕셔너리
    :return: 생성된 Firestore 문서의 고유 ID
    """
    try:
        db = firestore.client()
        
        # 공통 필드 추가
        data['created_at'] = DateTimeUtils.now()
        data['user_id'] = user_id
        
        # Firestore 호환 변환
        data = DateTimeUtils.for_firestore(data)
        
        # 컬렉션에 새 문서 추가
        doc_ref = db.collection(collection_name).document()
        doc_ref.set(data)
        
        logging.info(f"Firestore 저장 성공 (Collection: {collection_name}, Doc ID: {doc_ref.id})")
        return doc_ref.id

    except Exception as e:
        logging.error(f"Firestore 저장 실패 (Collection: {collection_name}): {e}", exc_info=True)
        raise