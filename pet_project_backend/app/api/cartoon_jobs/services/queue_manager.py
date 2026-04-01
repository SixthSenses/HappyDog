# app/api/cartoon_jobs/services/queue_manager.py
"""
Queue management layer for cartoon job processing (Phase 2-5: SRP compliance).

Responsibilities:
- ThreadPoolExecutor lifecycle management
- Job submission and cancellation
- Active job tracking
- Queue health monitoring

Does NOT handle:
- Business logic (job status, domain operations) -> JobHandler
- Notifications -> NotificationBroker
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, Optional


class CartoonQueueManager:
    """
    Manages background job queue using ThreadPoolExecutor.
    
    Responsibilities (SRP):
    - Submit jobs to background thread pool
    - Track active jobs (job_id -> Future mapping)
    - Cancel jobs
    - Provide queue health metrics (active count, queue size)
    """
    
    def __init__(self, max_workers: int = 3, executor: Optional[ThreadPoolExecutor] = None):
        """
        Initialize queue manager with executor.
        
        Args:
            max_workers: Maximum concurrent job workers
            executor: Optional ThreadPoolExecutor instance (None = docs mode)
        """
        self.max_workers = max_workers
        self.executor = executor if executor is not None else None
        self.docs_mode = self.executor is None
        self.active_jobs: Dict[str, Future] = {}
        self._lock = threading.Lock()
        
        if self.docs_mode:
            logging.info("CartoonQueueManager initialized in DOCS_MODE (no background execution)")
    
    def submit_job(self, job_id: str, task_callable, *args, **kwargs) -> Optional[Future]:
        """
        Submit a job to the background queue.
        
        Args:
            job_id: Unique job identifier for tracking
            task_callable: Function to execute in background
            *args, **kwargs: Arguments to pass to task_callable
        
        Returns:
            Future object or None (docs mode)
        """
        if self.docs_mode:
            logging.info(f"DOCS_MODE: submit_job no-op for job {job_id}")
            return None
        
        with self._lock:
            if job_id in self.active_jobs:
                logging.warning(f"Job already active: {job_id}")
                return self.active_jobs[job_id]
            
            future = self.executor.submit(task_callable, *args, **kwargs)
            self.active_jobs[job_id] = future
            
            # Auto-cleanup on completion
            future.add_done_callback(lambda f: self._cleanup_job(job_id))
            
            logging.info(f"Job submitted to queue: {job_id}")
            return future
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running job.
        
        Args:
            job_id: Job identifier to cancel
        
        Returns:
            True if cancelled successfully, False otherwise
        """
        if self.docs_mode:
            return False
        
        with self._lock:
            if job_id not in self.active_jobs:
                logging.warning(f"Cannot cancel: job not in active_jobs: {job_id}")
                return False
            
            future = self.active_jobs[job_id]
            if future.cancel():
                logging.info(f"Job cancelled: {job_id}")
                return True
            else:
                logging.warning(f"Cannot cancel already running job: {job_id}")
                return False
    
    def get_active_count(self) -> int:
        """Get number of currently active jobs."""
        if self.docs_mode:
            return 0
        with self._lock:
            return len(self.active_jobs)
    
    def get_queue_size(self) -> int:
        """Get approximate size of pending queue (active - max_workers)."""
        if self.docs_mode:
            return 0
        return max(0, len(self.active_jobs) - self.max_workers)
    
    def shutdown(self, wait: bool = True):
        """
        Shutdown the queue manager and executor.
        
        Args:
            wait: Whether to wait for active jobs to complete
        """
        if self.docs_mode:
            return
        
        logging.info("CartoonQueueManager shutting down...")
        self.executor.shutdown(wait=wait)
        
        with self._lock:
            self.active_jobs.clear()
        
        logging.info("CartoonQueueManager shutdown complete")
    
    def _cleanup_job(self, job_id: str):
        """Remove completed job from active tracking."""
        if self.docs_mode:
            return
        
        with self._lock:
            self.active_jobs.pop(job_id, None)
            logging.debug(f"Job removed from active_jobs: {job_id}")
    
    def __del__(self):
        """Destructor: ensure resources are cleaned up."""
        try:
            self.shutdown(wait=False)
        except:
            pass
