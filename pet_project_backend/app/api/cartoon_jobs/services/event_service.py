# app/api/cartoon_jobs/services/event_service.py

import logging
from typing import Dict, Any
from flask import Flask


class CartoonJobEventService:
    """
    만화 생성 작업의 생명주기 이벤트를 처리하는 서비스 클래스.
    순수한 Job CRUD와 외부 서비스 통합 사이의 오케스트레이션을 담당합니다.
    """
    
    def __init__(self):
        """기본 생성자."""
        self.app = None

    def init_app(self, app: Flask):
        """Flask 앱과 연결합니다."""
        self.app = app
        logging.info("CartoonJobEventService 초기화됨")

    def handle_job_created(self, job_data: Dict[str, Any]):
        """
        새로운 작업이 생성되었을 때 처리합니다.
        
        Args:
            job_data: 생성된 작업 정보
        """
        try:
            from flask import current_app
            
            job_id = job_data['job_id']
            image_url = job_data['image_url']
            user_text = job_data.get('user_text', '')
            
            logging.info(f"작업 생성 이벤트 처리 시작: {job_id}")
            
            # 백그라운드 작업 프로세서에 작업 제출
            job_processor = current_app.services['job_processor']
            future = job_processor.submit_job(job_id, image_url, user_text)
            
            logging.info(f"백그라운드 작업 제출 완료: {job_id}")
            
        except Exception as e:
            logging.error(f"작업 생성 이벤트 처리 실패 (job_id: {job_data.get('job_id')}): {e}", exc_info=True)
            raise

    def handle_job_processing(self, update_data: Dict[str, Any]):
        """
        작업이 처리 상태로 변경되었을 때 처리합니다.
        
        Args:
            update_data: 상태 업데이트 정보
        """
        try:
            job_id = update_data['job_id']
            logging.info(f"작업 처리 시작: {job_id}")
            
            # 현재는 로깅만 수행, 필요시 추가 처리 가능
            # 예: 처리 시작 알림, 모니터링 메트릭 업데이트 등
            
        except Exception as e:
            logging.error(f"작업 처리 이벤트 처리 실패 (job_id: {update_data.get('job_id')}): {e}", exc_info=True)

    def handle_job_completed(self, update_data: Dict[str, Any]):
        """
        작업이 성공적으로 완료되었을 때 처리합니다.
        
        Args:
            update_data: 완료된 작업 정보
        """
        try:
            from flask import current_app
            
            job = update_data['job']
            job_id = job['job_id']
            user_id = job['user_id']
            result_image_url = job.get('result_image_url')
            
            logging.info(f"작업 완료 이벤트 처리 시작: {job_id}")
            
            # Job Integration Service를 통한 후속 작업 처리
            job_integration = current_app.services['job_integration']
            
            # 1. 결과 게시물 생성
            post_result = job_integration.create_result_post(job, result_image_url)
            
            # 2. 완료 알림 발송
            job_integration.send_completion_notification(user_id, job_id, post_result)
            
            logging.info(f"작업 완료 처리 완료: {job_id}")
            
        except Exception as e:
            logging.error(f"작업 완료 이벤트 처리 실패 (job_id: {update_data.get('job_id')}): {e}", exc_info=True)

    def handle_job_failed(self, update_data: Dict[str, Any]):
        """
        작업이 실패했을 때 처리합니다.
        
        Args:
            update_data: 실패한 작업 정보
        """
        try:
            from flask import current_app
            
            job = update_data['job']
            job_id = job['job_id']
            user_id = job['user_id']
            error_message = job.get('error_message', '알 수 없는 오류가 발생했습니다')
            
            logging.info(f"작업 실패 이벤트 처리 시작: {job_id}")
            
            # Job Integration Service를 통한 실패 알림 발송
            job_integration = current_app.services['job_integration']
            job_integration.send_failure_notification(user_id, job_id, error_message)
            
            logging.info(f"작업 실패 처리 완료: {job_id}")
            
        except Exception as e:
            logging.error(f"작업 실패 이벤트 처리 실패 (job_id: {update_data.get('job_id')}): {e}", exc_info=True)

    def handle_job_cancelled(self, job_data: Dict[str, Any]):
        """
        작업이 취소되었을 때 처리합니다.
        
        Args:
            job_data: 취소된 작업 정보
        """
        try:
            from flask import current_app
            
            job_id = job_data['job_id']
            user_id = job_data['user_id']
            
            logging.info(f"작업 취소 이벤트 처리 시작: {job_id}")
            
            # 1. 백그라운드 프로세서에서 작업 취소 시도
            job_processor = current_app.services['job_processor']
            cancelled = job_processor.cancel_job(job_id)
            
            # 2. 작업 상태를 FAILED로 최종 변경 (취소도 일종의 실패)
            job_service = current_app.services['cartoon_jobs']
            from app.models.cartoon_job import CartoonJobStatus
            
            result_data = {
                'error_message': '사용자가 작업을 취소했습니다'
            }
            job_service.update_job_status(job_id, CartoonJobStatus.FAILED, result_data)
            
            # 3. 취소 알림 발송
            job_integration = current_app.services['job_integration']
            job_integration.send_failure_notification(user_id, job_id, "작업이 취소되었습니다")
            
            logging.info(f"작업 취소 처리 완료: {job_id} (백그라운드 취소: {cancelled})")
            
        except Exception as e:
            logging.error(f"작업 취소 이벤트 처리 실패 (job_id: {job_data.get('job_id')}): {e}", exc_info=True)

    def handle_job_status_updated(self, update_data: Dict[str, Any]):
        """
        작업 상태가 업데이트되었을 때 처리합니다 (일반적인 경우).
        
        Args:
            update_data: 상태 업데이트 정보
        """
        try:
            job_id = update_data['job_id']
            old_status = update_data['old_status']
            new_status = update_data['new_status']
            
            logging.info(f"작업 상태 변경: {job_id} ({old_status} -> {new_status})")
            
            # 특정 상태 변경에 대한 추가 처리가 필요하면 여기서 수행
            # 예: 메트릭 업데이트, 모니터링 알림 등
            
        except Exception as e:
            logging.error(f"작업 상태 업데이트 이벤트 처리 실패 (job_id: {update_data.get('job_id')}): {e}", exc_info=True)
