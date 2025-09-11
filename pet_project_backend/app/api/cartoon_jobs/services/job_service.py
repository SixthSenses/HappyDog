# app/api/cartoon_jobs/services/job_service.py

import logging
import uuid
from datetime import datetime, timezone
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any, List
from enum import Enum

from app.models.cartoon_job import CartoonJob, CartoonJobStatus


class CartoonJobService:
    """
    순수한 Cartoon Job CRUD 작업을 담당하는 서비스 클래스.
    백그라운드 처리, 알림, 외부 서비스 통합과는 완전히 분리되어 있습니다.
    """
    
    def __init__(self):
        """기본 생성자. 외부 서비스 의존성 없음."""
        self.db = firestore.client()
        self.jobs_ref = self.db.collection('cartoon_jobs')

    def init_app(self, app):
        """Flask 앱 초기화 (필요 시 설정 로드)."""
        self.app = app

    def create_job(self, user_id: str, image_url: str, user_text: str = "") -> Dict[str, Any]:
        """
        새로운 만화 생성 작업을 생성합니다.
        
        Args:
            user_id: 작업을 요청한 사용자 ID
            image_url: 변환할 원본 이미지 URL
            user_text: 사용자가 입력한 텍스트 (선택사항)
            
        Returns:
            생성된 작업 정보와 이벤트 데이터
        """
        try:
            job_id = str(uuid.uuid4())
            
            new_job = CartoonJob(
                job_id=job_id,
                user_id=user_id,
                status=CartoonJobStatus.PENDING,  # 초기 상태는 PENDING
                original_image_url=image_url,
                user_text=user_text,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            job_dict = asdict(new_job)
            job_dict['status'] = new_job.status.value  # Enum을 문자열로 변환
            
            # Firestore에 저장
            self.jobs_ref.document(job_id).set(job_dict)
            logging.info(f"만화 생성 작업 생성됨 (Job ID: {job_id}) for user {user_id}")
            
            # 이벤트 처리를 위한 데이터 반환
            return {
                'job': job_dict,
                'event_type': 'job_created',
                'user_id': user_id,
                'job_id': job_id,
                'image_url': image_url,
                'user_text': user_text
            }
            
        except Exception as e:
            logging.error(f"Firestore 작업 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_job_status(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 ID와 사용자 ID로 작업 상태를 조회합니다.
        
        Args:
            job_id: 조회할 작업 ID
            user_id: 작업 소유자 ID (권한 확인)
            
        Returns:
            작업 정보 또는 None
        """
        try:
            doc = self.jobs_ref.document(job_id).get()
            if doc.exists and doc.to_dict().get('user_id') == user_id:
                return doc.to_dict()
            return None
        except Exception as e:
            logging.error(f"작업 조회 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise

    def update_job_status(self, job_id: str, status: CartoonJobStatus, 
                         result_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        작업 상태를 업데이트합니다.
        
        Args:
            job_id: 업데이트할 작업 ID
            status: 새로운 상태
            result_data: 추가 결과 데이터 (선택사항)
            
        Returns:
            업데이트된 작업 정보와 이벤트 데이터
        """
        try:
            job_ref = self.jobs_ref.document(job_id)
            job_doc = job_ref.get()
            
            if not job_doc.exists:
                raise ValueError(f"작업을 찾을 수 없습니다: {job_id}")
            
            job_data = job_doc.to_dict()
            current_status = job_data.get('status')
            
            # 상태 업데이트 데이터 준비
            update_data = {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc)
            }
            
            # 추가 결과 데이터가 있으면 포함
            if result_data:
                update_data.update(result_data)
            
            job_ref.update(update_data)
            
            # 업데이트된 데이터 조회
            updated_job = job_ref.get().to_dict()
            
            logging.info(f"작업 상태 업데이트: {job_id} ({current_status} -> {status.value})")
            
            # 이벤트 처리를 위한 데이터 반환
            return {
                'job': updated_job,
                'event_type': 'job_status_updated',
                'job_id': job_id,
                'user_id': job_data.get('user_id'),
                'old_status': current_status,
                'new_status': status.value,
                'result_data': result_data
            }
            
        except Exception as e:
            logging.error(f"작업 상태 업데이트 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise

    def get_user_jobs(self, user_id: str, limit: int = 20, 
                      status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        사용자의 작업 목록을 조회합니다.
        
        Args:
            user_id: 사용자 ID
            limit: 최대 조회 개수
            status_filter: 상태 필터 (선택사항)
            
        Returns:
            작업 목록
        """
        try:
            query = self.jobs_ref.where('user_id', '==', user_id).order_by('created_at', direction=firestore.Query.DESCENDING).limit(limit)
            
            if status_filter:
                query = query.where('status', '==', status_filter)
            
            docs = query.get()
            jobs = [doc.to_dict() for doc in docs]
            
            logging.info(f"사용자 작업 조회 완료 (user_id: {user_id}, count: {len(jobs)})")
            return jobs
            
        except Exception as e:
            logging.error(f"사용자 작업 조회 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def cancel_job(self, job_id: str, user_id: str) -> Dict[str, Any]:
        """
        진행 중인 작업을 취소 상태로 변경합니다.
        
        Args:
            job_id: 취소할 작업 ID
            user_id: 작업 소유자 ID (권한 확인)
            
        Returns:
            업데이트된 작업 정보와 이벤트 데이터
        """
        try:
            job_ref = self.jobs_ref.document(job_id)
            job_doc = job_ref.get()

            if not job_doc.exists:
                raise ValueError("취소할 작업을 찾을 수 없습니다.")

            job_data = job_doc.to_dict()
            if job_data.get('user_id') != user_id:
                raise PermissionError("작업을 취소할 권한이 없습니다.")

            current_status = job_data.get('status')
            if current_status not in [CartoonJobStatus.PENDING.value, CartoonJobStatus.PROCESSING.value]:
                raise ValueError(f"현재 '{current_status}' 상태의 작업은 취소할 수 없습니다.")
            
            # 상태를 CANCELING으로 업데이트
            update_data = {
                "status": CartoonJobStatus.CANCELING.value,
                "updated_at": datetime.now(timezone.utc)
            }
            job_ref.update(update_data)
            
            updated_job = job_ref.get().to_dict()
            logging.info(f"만화 생성 작업 취소 요청됨 (Job ID: {job_id})")
            
            # 이벤트 처리를 위한 데이터 반환
            return {
                'job': updated_job,
                'event_type': 'job_cancelled',
                'job_id': job_id,
                'user_id': user_id,
                'old_status': current_status,
                'new_status': CartoonJobStatus.CANCELING.value
            }
            
        except Exception as e:
            logging.error(f"작업 취소 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        작업 ID로 작업을 조회합니다 (권한 확인 없음, 내부용).
        
        Args:
            job_id: 조회할 작업 ID
            
        Returns:
            작업 정보 또는 None
        """
        try:
            doc = self.jobs_ref.document(job_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            logging.error(f"작업 조회 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise
