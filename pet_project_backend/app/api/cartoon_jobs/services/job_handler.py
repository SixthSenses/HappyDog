# app/api/cartoon_jobs/services/job_handler.py
"""
Job handling layer for cartoon processing (Phase 2-5: SRP compliance).

Responsibilities:
- Execute cartoon generation workflow
- Coordinate between job service, OpenAI service, storage service
- Handle job status transitions (PROCESSING -> COMPLETED/FAILED)
- Check cancellation state at critical points

Does NOT handle:
- Thread pool management -> QueueManager
- Notification logic -> NotificationBroker (via events)
"""

import logging
from typing import Dict, Any, Optional
from flask import Flask, current_app

from app.models.cartoon_job import CartoonJobStatus


class CartoonJobHandler:
    """
    Handles business logic for cartoon job processing.
    
    Responsibilities (SRP):
    - Orchestrate cartoon generation workflow
    - Check job cancellation status
    - Update job status via job_service
    - Invoke OpenAI service with storage service
    - Trigger job events (processing, completed, failed, cancelled)
    """
    
    def __init__(self):
        """Initialize job handler (lightweight, no heavy dependencies)."""
        self.app: Optional[Flask] = None
    
    def init_app(self, app: Flask):
        """Connect to Flask app context."""
        self.app = app
        logging.info("CartoonJobHandler initialized")
    
    def process_job(self, job_id: str, image_url: str, user_text: str = "") -> Dict[str, Any]:
        """
        Process a cartoon generation job within Flask app context.
        
        Workflow:
        1. Check if job exists and is not cancelled
        2. Update status to PROCESSING, trigger event
        3. Invoke OpenAI service to generate cartoon
        4. Re-check cancellation (prevent race condition)
        5. Update status to COMPLETED/FAILED, trigger event
        
        Args:
            job_id: Job identifier
            image_url: Source image URL for cartoonization
            user_text: Optional user prompt text
        
        Returns:
            Dict with success status and result/error details
        """
        if not self.app:
            raise RuntimeError("CartoonJobHandler not initialized with Flask app")
        
        with self.app.app_context():
            try:
                job_service = current_app.services['cartoon_jobs']
                job_events = current_app.services['job_events']
                
                # Step 1: Check job exists and is not cancelled
                job_data = job_service.get_job_by_id(job_id)
                if not job_data:
                    logging.error(f"Job not found: {job_id}")
                    return {"success": False, "error": "작업을 찾을 수 없습니다"}
                
                if self._is_cancelled(job_data):
                    logging.info(f"Job already cancelled/canceling: {job_id}")
                    if job_data.get('status') == CartoonJobStatus.CANCELING.value:
                        job_events.handle_job_cancelled(job_data)
                    return {"success": False, "error": "작업이 취소되었습니다"}
                
                # Step 2: Update to PROCESSING
                update_data = job_service.update_job_status(job_id, CartoonJobStatus.PROCESSING)
                job_events.handle_job_processing(update_data)
                
                # Step 3: Generate cartoon via OpenAI (with storage service injection)
                openai_service = current_app.services['openai']
                storage_service = current_app.services['storage']
                result = openai_service.generate_cartoon(
                    image_url,
                    user_text,
                    storage_service=storage_service
                )
                
                # Step 4: Re-check cancellation before finalizing (race condition prevention)
                job_data = job_service.get_job_by_id(job_id)
                if not job_data:
                    logging.error(f"Job not found before finalization: {job_id}")
                    return {"success": False, "error": "작업을 찾을 수 없습니다"}
                
                if self._is_cancelled(job_data):
                    logging.info(f"Job cancelled before completion: {job_id}")
                    if job_data.get('status') == CartoonJobStatus.CANCELING.value:
                        job_events.handle_job_cancelled(job_data)
                    return {"success": False, "error": "작업이 취소되었습니다"}
                
                # Step 5: Finalize result (COMPLETED or FAILED)
                if result['success']:
                    return self._handle_success(job_id, result, job_service, job_events)
                else:
                    return self._handle_failure(job_id, result, job_service, job_events)
                
            except Exception as e:
                logging.error(f"Exception during job processing: {job_id}: {e}", exc_info=True)
                return self._handle_exception(job_id, e)
    
    def _is_cancelled(self, job_data: Dict[str, Any]) -> bool:
        """Check if job is in cancelled or canceling state."""
        status = job_data.get('status')
        return status in (CartoonJobStatus.CANCELING.value, CartoonJobStatus.CANCELLED.value)
    
    def _handle_success(self, job_id: str, result: Dict[str, Any], job_service, job_events) -> Dict[str, Any]:
        """Handle successful job completion."""
        result_data = {'result_image_url': result['image_url']}
        update_data = job_service.update_job_status(
            job_id,
            CartoonJobStatus.COMPLETED,
            result_data
        )
        job_events.handle_job_completed(update_data)
        
        logging.info(f"Cartoon job completed successfully: {job_id}")
        return {"success": True, "result": result}
    
    def _handle_failure(self, job_id: str, result: Dict[str, Any], job_service, job_events) -> Dict[str, Any]:
        """Handle job failure (OpenAI error)."""
        error_message = result.get('error', '알 수 없는 오류가 발생했습니다')
        result_data = {'error_message': error_message}
        update_data = job_service.update_job_status(
            job_id,
            CartoonJobStatus.FAILED,
            result_data
        )
        job_events.handle_job_failed(update_data)
        
        logging.error(f"Cartoon job failed: {job_id}, error: {error_message}")
        return {"success": False, "error": error_message}
    
    def _handle_exception(self, job_id: str, exception: Exception) -> Dict[str, Any]:
        """Handle unexpected exception during job processing."""
        try:
            job_service = current_app.services['cartoon_jobs']
            job_events = current_app.services['job_events']
            
            result_data = {'error_message': f'처리 중 오류 발생: {str(exception)}'}
            update_data = job_service.update_job_status(
                job_id,
                CartoonJobStatus.FAILED,
                result_data
            )
            job_events.handle_job_failed(update_data)
        except:
            logging.error(f"Failed to handle exception for job: {job_id}", exc_info=True)
        
        return {"success": False, "error": str(exception)}
