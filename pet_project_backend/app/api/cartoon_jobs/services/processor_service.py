# app/api/cartoon_jobs/services/processor_service.py

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Any, Optional
from flask import Flask

from app.models.cartoon_job import CartoonJobStatus


class CartoonJobProcessor:
    """
    백그라운드 작업 처리를 담당하는 서비스 클래스.
    ThreadPoolExecutor를 사용하여 만화 생성 작업을 비동기적으로 처리합니다.
    """
    
    def __init__(self, max_workers: int = 3):
        """
        백그라운드 작업 프로세서를 초기화합니다.
        
        Args:
            max_workers: 동시 처리 가능한 최대 작업 수
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.app = None
        self.active_jobs = {}  # job_id -> Future 매핑
        self._lock = threading.Lock()

    def init_app(self, app: Flask):
        """Flask 앱과 연결합니다."""
        self.app = app
        logging.info(f"CartoonJobProcessor 초기화됨 (max_workers: {self.max_workers})")

    def submit_job(self, job_id: str, image_url: str, user_text: str = "") -> Future:
        """
        작업을 백그라운드 큐에 제출합니다.
        
        Args:
            job_id: 처리할 작업 ID
            image_url: 변환할 이미지 URL
            user_text: 사용자 입력 텍스트
            
        Returns:
            Future 객체
        """
        with self._lock:
            if job_id in self.active_jobs:
                logging.warning(f"이미 처리 중인 작업입니다: {job_id}")
                return self.active_jobs[job_id]
            
            future = self.executor.submit(self._process_job, job_id, image_url, user_text)
            self.active_jobs[job_id] = future
            
            # 완료 시 active_jobs에서 제거하는 콜백 추가
            future.add_done_callback(lambda f: self._cleanup_job(job_id))
            
            logging.info(f"백그라운드 작업 제출됨: {job_id}")
            return future

    def _process_job(self, job_id: str, image_url: str, user_text: str) -> Dict[str, Any]:
        """
        실제 작업을 처리하는 내부 메서드.
        Flask 앱 컨텍스트 내에서 실행됩니다.
        
        Args:
            job_id: 처리할 작업 ID
            image_url: 변환할 이미지 URL
            user_text: 사용자 입력 텍스트
            
        Returns:
            처리 결과
        """
        if not self.app:
            raise RuntimeError("Flask 앱이 초기화되지 않았습니다")
            
        with self.app.app_context():
            try:
                from flask import current_app
                
                # 1. 작업 상태를 PROCESSING으로 업데이트
                job_service = current_app.services['cartoon_jobs']
                job_events = current_app.services['job_events']
                
                # 작업이 취소되었는지 확인
                job_data = job_service.get_job_by_id(job_id)
                if not job_data:
                    logging.error(f"작업을 찾을 수 없음: {job_id}")
                    return {"success": False, "error": "작업을 찾을 수 없습니다"}
                
                if job_data.get('status') == CartoonJobStatus.CANCELING.value:
                    logging.info(f"취소 요청으로 작업 중단: {job_id}")
                    job_events.handle_job_cancelled(job_data)
                    return {"success": False, "error": "작업이 취소되었습니다"}
                
                # 상태를 PROCESSING으로 변경
                update_data = job_service.update_job_status(job_id, CartoonJobStatus.PROCESSING)
                job_events.handle_job_processing(update_data)
                
                # 2. OpenAI 서비스로 만화 생성
                openai_service = current_app.services['openai']
                result = openai_service.generate_cartoon(image_url, user_text)
                
                # 3. 완료 전 취소 상태 재확인 (경쟁 상태 방지)
                job_data = job_service.get_job_by_id(job_id)
                if not job_data:
                    logging.error(f"작업을 찾을 수 없음(완료 전): {job_id}")
                    return {"success": False, "error": "작업을 찾을 수 없습니다"}
                    
                if job_data.get('status') == CartoonJobStatus.CANCELING.value:
                    logging.info(f"취소 요청으로 작업 중단(완료 전): {job_id}")
                    job_events.handle_job_cancelled(job_data)
                    return {"success": False, "error": "작업이 취소되었습니다"}
                
                # 4. 결과 처리
                if result['success']:
                    # 성공 처리
                    result_data = {
                        'result_image_url': result['image_url']
                    }
                    update_data = job_service.update_job_status(
                        job_id, 
                        CartoonJobStatus.COMPLETED, 
                        result_data
                    )
                    job_events.handle_job_completed(update_data)
                    
                    logging.info(f"만화 생성 작업 완료: {job_id}")
                    return {"success": True, "result": result}
                else:
                    # 실패 처리
                    error_message = result.get('error', '알 수 없는 오류가 발생했습니다')
                    result_data = {
                        'error_message': error_message
                    }
                    update_data = job_service.update_job_status(
                        job_id, 
                        CartoonJobStatus.FAILED, 
                        result_data
                    )
                    job_events.handle_job_failed(update_data)
                    
                    logging.error(f"만화 생성 작업 실패: {job_id}, 오류: {error_message}")
                    return {"success": False, "error": error_message}
                    
            except Exception as e:
                logging.error(f"만화 작업 처리 중 예외 발생 (job_id: {job_id}): {e}", exc_info=True)
                
                # 예외 발생 시 실패 처리
                try:
                    job_service = current_app.services['cartoon_jobs']
                    job_events = current_app.services['job_events']
                    
                    result_data = {
                        'error_message': f'처리 중 오류 발생: {str(e)}'
                    }
                    update_data = job_service.update_job_status(
                        job_id, 
                        CartoonJobStatus.FAILED, 
                        result_data
                    )
                    job_events.handle_job_failed(update_data)
                except:
                    logging.error(f"실패 처리 중 추가 오류 발생: {job_id}", exc_info=True)
                
                return {"success": False, "error": str(e)}

    def _cleanup_job(self, job_id: str):
        """완료된 작업을 active_jobs에서 제거합니다."""
        with self._lock:
            self.active_jobs.pop(job_id, None)
            logging.debug(f"Active jobs에서 제거됨: {job_id}")

    def cancel_job(self, job_id: str) -> bool:
        """
        실행 중인 작업을 취소합니다.
        
        Args:
            job_id: 취소할 작업 ID
            
        Returns:
            취소 성공 여부
        """
        with self._lock:
            if job_id in self.active_jobs:
                future = self.active_jobs[job_id]
                if future.cancel():
                    logging.info(f"백그라운드 작업 취소됨: {job_id}")
                    return True
                else:
                    logging.warning(f"이미 실행 중인 작업은 취소할 수 없음: {job_id}")
                    return False
            else:
                logging.warning(f"취소할 작업이 active_jobs에 없음: {job_id}")
                return False

    def get_active_count(self) -> int:
        """현재 실행 중인 작업 수를 반환합니다."""
        with self._lock:
            return len(self.active_jobs)

    def get_queue_size(self) -> int:
        """대기 중인 작업 수를 반환합니다."""
        # ThreadPoolExecutor의 내부 큐 크기를 정확히 알기 어려우므로 근사치 반환
        return max(0, len(self.active_jobs) - self.max_workers)

    def shutdown(self, wait: bool = True):
        """
        프로세서를 종료합니다.
        
        Args:
            wait: 실행 중인 작업 완료를 기다릴지 여부
        """
        logging.info("CartoonJobProcessor 종료 중...")
        self.executor.shutdown(wait=wait)
        with self._lock:
            self.active_jobs.clear()
        logging.info("CartoonJobProcessor 종료됨")

    def __del__(self):
        """소멸자에서 리소스 정리."""
        try:
            self.shutdown(wait=False)
        except:
            pass
