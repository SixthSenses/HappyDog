# app/api/cartoon_jobs/services/processor_service.py
"""
Refactored Cartoon Job Processor - Facade Pattern (Phase 2-5: SRP + OCP).

Original monolithic class decomposed into 3 layers:
- QueueManager: ThreadPool management, job submission/cancellation
- JobHandler: Business logic for cartoon generation workflow
- NotificationBroker: (handled via JobEvents, no separate layer needed)

This file maintains backward-compatible facade for existing code.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional
from flask import Flask

from app.api.cartoon_jobs.services.queue_manager import CartoonQueueManager
from app.api.cartoon_jobs.services.job_handler import CartoonJobHandler


class CartoonJobProcessor:
    """
    Facade for cartoon job background processing.
    
    Phase 2-5 Refactoring:
    - Delegates queue management to CartoonQueueManager (SRP)
    - Delegates job workflow to CartoonJobHandler (SRP)
    - Maintains backward-compatible API for existing routes
    
    Responsibilities (after refactoring):
    - Coordinate between queue manager and job handler
    - Provide unified interface for job submission/cancellation
    - Maintain app context lifecycle
    """
    
    def __init__(self, max_workers: int = 3, executor: Optional[ThreadPoolExecutor] = None):
        """
        Initialize processor facade with queue manager and job handler.
        
        Args:
            max_workers: Maximum concurrent workers (passed to queue manager)
            executor: Optional ThreadPoolExecutor (None = docs mode)
        """
        # Phase 2-5: Delegate to specialized layers
        self.queue_manager = CartoonQueueManager(max_workers=max_workers, executor=executor)
        self.job_handler = CartoonJobHandler()
        
        self.max_workers = max_workers
        self.docs_mode = self.queue_manager.docs_mode
        
        if self.docs_mode:
            logging.info("CartoonJobProcessor initialized in DOCS_MODE (background execution disabled)")

    def init_app(self, app: Flask):
        """Initialize Flask app context for job handler."""
        self.job_handler.init_app(app)
        logging.info(f"CartoonJobProcessor 초기화됨 (max_workers: {self.max_workers})")

    def submit_job(self, job_id: str, image_url: str, user_text: str = "") -> Optional[Future]:
        """
        Submit job to background queue (backward-compatible facade method).
        
        Phase 2-5: Delegates to queue_manager for thread pool submission,
        wraps job_handler.process_job as the task callable.
        
        Args:
            job_id: Job identifier
            image_url: Source image URL
            user_text: Optional user prompt
        
        Returns:
            Future object or None (docs mode)
        """
        if self.docs_mode:
            logging.info("DOCS_MODE: submit_job no-op returning dummy future result")
            class _ImmediateFuture:
                def result(self):
                    return {"success": True, "skipped": True}
            return _ImmediateFuture()
        
        # Phase 2-5: Delegate to queue manager, pass job_handler's process_job as callable
        return self.queue_manager.submit_job(
            job_id,
            self.job_handler.process_job,  # task callable
            job_id, image_url, user_text    # arguments to process_job
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job (delegates to queue manager)."""
        return self.queue_manager.cancel_job(job_id)
    
    def get_active_count(self) -> int:
        """Get active job count (delegates to queue manager)."""
        return self.queue_manager.get_active_count()
    
    def get_queue_size(self) -> int:
        """Get queue size (delegates to queue manager)."""
        return self.queue_manager.get_queue_size()
    
    def shutdown(self, wait: bool = True):
        """Shutdown processor (delegates to queue manager)."""
        self.queue_manager.shutdown(wait=wait)
    
    def __del__(self):
        """Destructor: cleanup resources."""
        try:
            self.shutdown(wait=False)
        except:
            pass
