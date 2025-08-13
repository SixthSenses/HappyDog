# app/api/cartoon_jobs/services.py
import logging
import uuid
from datetime import datetime
from firebase_admin import firestore
from dataclasses import asdict
from typing import Optional, Dict, Any

from app.models.cartoon_job import CartoonJob, CartoonJobStatus

class CartoonJobService:
    """
    비동기 만화 생성 작업 관련 비즈니스 로직을 담당하는 서비스 클래스.
    """
    def __init__(self):
        self.db = firestore.client()
        self.jobs_ref = self.db.collection('cartoon_jobs')

    def create_cartoon_job(self, user_id: str, image_url: str) -> Dict[str, Any]:
        """
        만화 변환 작업을 Firestore에 등록하고 즉시 job 정보를 반환합니다.
        실제 이미지 변환은 이 문서 생성을 트리거로 하는 Cloud Function이 처리합니다.
        
        :param user_id: 작업을 요청한 사용자 ID
        :param image_url: 변환할 원본 이미지의 URL
        :return: 생성된 작업 정보 딕셔너리
        """
        try:
            job_id = str(uuid.uuid4())
            new_job = CartoonJob(
                job_id=job_id,
                user_id=user_id,
                status=CartoonJobStatus.PROCESSING,
                original_image_url=image_url,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            job_dict = asdict(new_job)
            # Enum 멤버를 문자열 값으로 변환하여 저장
            job_dict['status'] = new_job.status.value
            
            self.jobs_ref.document(job_id).set(job_dict)
            logging.info(f"만화 생성 작업 등록됨 (Job ID: {job_id}) for user {user_id}")
            return job_dict
        except Exception as e:
            logging.error(f"Firestore 작업 생성 실패 (user_id: {user_id}): {e}", exc_info=True)
            raise

    def get_job_by_id_and_owner(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """작업 ID로 문서를 조회하되, 소유주가 일치하는지 확인합니다."""
        try:
            doc = self.jobs_ref.document(job_id).get()
            if doc.exists and doc.to_dict().get('user_id') == user_id:
                return doc.to_dict()
            return None
        except Exception as e:
            logging.error(f"작업 조회 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise

    def cancel_cartoon_job(self, user_id: str, job_id: str) -> Dict[str, Any]:
        """
        진행 중인 만화 생성 작업을 'canceling' 상태로 변경합니다.
        
        :param user_id: 작업을 요청한 사용자 ID (소유권 확인용)
        :param job_id: 취소할 작업의 ID
        :return: 상태가 변경된 작업 정보 딕셔너리
        """
        job_ref = self.jobs_ref.document(job_id)
        job_doc = job_ref.get()

        if not job_doc.exists:
            raise FileNotFoundError("취소할 작업을 찾을 수 없습니다.")

        job_data = job_doc.to_dict()
        if job_data.get('user_id') != user_id:
            raise PermissionError("작업을 취소할 권한이 없습니다.")

        current_status = job_data.get('status')
        if current_status != CartoonJobStatus.PROCESSING.value:
            raise ValueError(f"현재 '{current_status}' 상태의 작업은 취소할 수 없습니다.")
        
        try:
            # 상태를 'canceling'으로 업데이트. Cloud Function이 이 상태를 감지하고 작업을 중단합니다.
            update_data = {
                "status": CartoonJobStatus.CANCELING.value,
                "updated_at": datetime.utcnow()
            }
            job_ref.update(update_data)
            
            updated_job = job_ref.get().to_dict()
            logging.info(f"만화 생성 작업 취소 요청됨 (Job ID: {job_id})")
            return updated_job
        except Exception as e:
            logging.error(f"작업 취소 상태 업데이트 실패 (job_id: {job_id}): {e}", exc_info=True)
            raise

# 서비스 인스턴스는 app/__init__.py에서 생성 및 주입됩니다.
cartoon_job_service: Optional[CartoonJobService] = None