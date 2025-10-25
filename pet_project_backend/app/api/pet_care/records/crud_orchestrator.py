"""Pet Care CRUD Orchestrator.

Coordinates basic CRUD operations without business logic like goal tracking.
This service is responsible for orchestrating record creation, updates, and deletion
with cache invalidation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils import metrics


class PetCareCrudOrchestrator:
    """Orchestrates CRUD operations with cache coordination.
    
    This service focuses purely on coordinating CRUD operations and cache invalidation,
    without business logic like goal analysis or notifications.
    """

    def __init__(self, crud_service, query_service, cache_service=None):
        """Initialize orchestrator with dependencies.
        
        Args:
            crud_service: CRUD operations service
            query_service: Query operations service
            cache_service: Optional cache service for invalidation
        """
        self.crud = crud_service
        self.query = query_service
        self.cache = cache_service
        logging.info("PetCareCrudOrchestrator initialized.")

    def create_record(self, pet_id: str, record_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a record with cache invalidation.
        
        Args:
            pet_id: The pet's unique identifier
            record_data: Validated record data
            
        Returns:
            dict: Created record
        """
        try:
            # Create the record
            result = self.crud.create_record(pet_id, record_data)
            
            # Invalidate affected caches
            search_date = result.get('searchDate')
            if search_date and self.cache:
                affected_dates = [search_date]
                try:
                    self.cache.invalidate_affected_caches(pet_id, affected_dates)
                except Exception as ce:
                    logging.warning(f"Cache invalidation failed for pet {pet_id}, dates={affected_dates}: {ce}")
                
            metrics.increment('pet_care_record_created', record_type=record_data['record_type'])
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to create record for pet {pet_id}: {e}", exc_info=True)
            raise

    def update_record(self, pet_id: str, log_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a record with cache invalidation.
        
        Args:
            pet_id: The pet's unique identifier
            log_id: Record identifier
            update_data: Data to update
            
        Returns:
            dict: Updated record
        """
        try:
            result = self.crud.update_record(pet_id, log_id, update_data)
            
            # Invalidate affected caches
            search_date = result.get('searchDate')
            if search_date and self.cache:
                affected_dates = [search_date]
                try:
                    self.cache.invalidate_affected_caches(pet_id, affected_dates)
                except Exception as ce:
                    logging.warning(f"Cache invalidation failed for pet {pet_id}, dates={affected_dates}: {ce}")
                
            metrics.increment('pet_care_record_updated')
            
            return result
            
        except Exception as e:
            logging.error(f"Failed to update record for pet {pet_id}: {e}", exc_info=True)
            raise

    def delete_record(self, pet_id: str, log_id: str, search_date: Optional[str] = None) -> None:
        """Delete a record with cache invalidation.
        
        Args:
            pet_id: The pet's unique identifier
            log_id: Record identifier
            search_date: Optional date for cache invalidation
        """
        try:
            self.crud.delete_record(pet_id, log_id)
            
            # Invalidate affected caches
            if search_date and self.cache:
                affected_dates = [search_date]
                try:
                    self.cache.invalidate_affected_caches(pet_id, affected_dates)
                except Exception as ce:
                    logging.warning(f"Cache invalidation failed for pet {pet_id}, dates={affected_dates}: {ce}")
                
            metrics.increment('pet_care_record_deleted')
            
        except Exception as e:
            logging.error(f"Failed to delete record for pet {pet_id}: {e}", exc_info=True)
            raise

    def get_daily_records(self, pet_id: str, date: str) -> Dict[str, Any]:
        """Get daily records summary.
        
        Args:
            pet_id: The pet's unique identifier
            date: Date in YYYY-MM-DD format
            
        Returns:
            dict: Daily records summary
        """
        try:
            records_result = self.query.get_daily(pet_id, date)
            
            summary = {
                'date': date,
                'records': records_result.get('records', []),
                'record_counts': self._count_by_type(records_result.get('records', [])),
                'meta': records_result.get('summary', {})
            }
            
            metrics.increment('daily_records_retrieved')
            
            return summary
            
        except Exception as e:
            logging.error(f"Failed to get daily records for pet {pet_id}, date {date}: {e}", exc_info=True)
            raise

    def _count_by_type(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count records by type.
        
        Args:
            records: List of records
            
        Returns:
            dict: Count by record type
        """
        counts = {}
        for record in records:
            record_type = record.get('record_type')
            if record_type:
                counts[record_type] = counts.get(record_type, 0) + 1
        return counts
