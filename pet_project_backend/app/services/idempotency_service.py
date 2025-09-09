import logging
import datetime
from typing import Callable, Tuple, Any, Dict
from firebase_admin import firestore
from google.api_core import exceptions as gexc

from app.utils.canonical_json import compute_canonical_hash, canonical_json_dumps


class IdempotencyService:
    """Firestore 기반 멱등 처리 서비스.

    컬렉션: idempotency_keys
    문서 구조:
      key: 헤더 X-Idempotency-Key 값 (document id)
      method, path
      request_hash: canonical body hash (sha256)
      response_body: 원본 JSON(dict) 직렬화 가능 구조
      status_code: int
      created_at: Firestore Timestamp
    """

    COLLECTION_NAME = 'idempotency_keys'

    def __init__(self):
        self.db = firestore.client()
        self.col = self.db.collection(self.COLLECTION_NAME)

    def execute(self, *, key: str, method: str, path: str, request_body: Any, handler: Callable[[], Tuple[Dict[str, Any], int]]) -> Tuple[Dict[str, Any], int, bool]:
        """핸들러를 멱등 실행.

        Returns: (response_body, status_code, reused)
        reused=True 이면 저장된 응답 리턴.
        해시 불일치 시 409 발생.
        """
        if not key:
            raise ValueError("idempotency key required")

        body_hash = compute_canonical_hash(request_body) if request_body is not None else compute_canonical_hash({})
        doc_ref = self.col.document(key)

        snapshot = doc_ref.get()
        if snapshot.exists:
            stored = snapshot.to_dict()
            stored_hash = stored.get('request_hash')
            if stored_hash != body_hash:
                # 동일 키인데 페이로드가 변경됨 => 충돌
                logging.warning(f"Idempotency hash mismatch key={key} stored={stored_hash} incoming={body_hash}")
                from werkzeug.exceptions import Conflict
                raise Conflict(description='Idempotency key reuse with different payload.')
            return stored.get('response_body', {}), int(stored.get('status_code', 200)), True

        # 새 키: 핸들러 실행 후 저장 (경쟁 조건 완화 위해 create 사용)
        response_body, status_code = handler()
        data = {
            'key': key,
            'method': method,
            'path': path,
            'request_hash': body_hash,
            'response_body': response_body,
            'status_code': status_code,
            'created_at': datetime.datetime.utcnow()
        }
        try:
            # create -> 이미 있으면 에러
            doc_ref.create(data)
        except gexc.AlreadyExists:
            # 경합: 다시 읽고 검증
            snapshot = doc_ref.get()
            stored = snapshot.to_dict()
            if stored.get('request_hash') != body_hash:
                from werkzeug.exceptions import Conflict
                raise Conflict(description='Idempotency key race with different payload.')
            return stored.get('response_body', {}), int(stored.get('status_code', 200)), True
        return response_body, status_code, False
