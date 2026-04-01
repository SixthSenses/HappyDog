"""Pet Care Goal Analyzer Coordinator.

Coordinates goal analysis with record data and settings.
This service is responsible for analyzing goal progress and preparing
goal-related data for presentation.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.utils import metrics


class PetCareGoalCoordinator:
    """Coordinates goal analysis across records and settings.
    
    This service focuses on goal tracking and analysis coordination,
    preparing enriched data with goal progress information.
    """

    def __init__(self, query_service, settings_service, goal_analyzer):
        """Initialize coordinator with dependencies.
        
        Args:
            query_service: Query operations service
            settings_service: Pet care settings service
            goal_analyzer: GoalAnalyzer instance
        """
        self.query = query_service
        self.settings = settings_service
        self.goal_analyzer = goal_analyzer
        logging.info("PetCareGoalCoordinator initialized.")

    def enrich_with_goal_analysis(
        self, 
        pet_id: str, 
        record_result: Dict[str, Any], 
        date: str
    ) -> Dict[str, Any]:
        """Enrich record result with goal analysis.
        
        Args:
            pet_id: The pet's unique identifier
            record_result: Record creation result
            date: Date for goal analysis
            
        Returns:
            dict: Enriched result with goal_analysis field
        """
        try:
            settings = self.settings.get_settings(pet_id)
            
            if settings and date:
                # Get all records for the date
                daily_records = self.query.get_daily(pet_id, date)['records']
                
                # Analyze goals
                goal_analysis = self.goal_analyzer.analyze_daily(
                    daily_records,
                    date,
                    settings,
                )
                record_result['goal_analysis'] = goal_analysis
                
                metrics.increment('goal_analysis_performed')
                
            return record_result
            
        except Exception as e:
            logging.error(f"Failed to enrich with goal analysis for pet {pet_id}, date {date}: {e}", exc_info=True)
            # Return original result without goal analysis on error
            return record_result

    def get_daily_goal_progress(self, pet_id: str, date: str) -> Optional[Dict[str, Any]]:
        """Get goal progress for a specific date.
        
        Args:
            pet_id: The pet's unique identifier
            date: Date in YYYY-MM-DD format
            
        Returns:
            dict: Goal progress or None if no settings
        """
        try:
            settings = self.settings.get_settings_at_date(pet_id, date)
            
            if not settings:
                return None
            
            records_result = self.query.get_daily(pet_id, date)
            goal_progress = self.goal_analyzer.analyze_daily(
                records_result['records'], 
                date, 
                settings
            )
            
            metrics.increment('daily_goal_progress_retrieved')
            
            return goal_progress
            
        except Exception as e:
            logging.error(f"Failed to get goal progress for pet {pet_id}, date {date}: {e}", exc_info=True)
            return None

    def check_goal_achievements(
        self, 
        goal_analysis: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Check which goals were achieved.
        
        Args:
            goal_analysis: Goal analysis result from analyzer
            
        Returns:
            dict: Mapping of goal type to achievement status
        """
        achievements = {}
        
        if 'achievements' in goal_analysis:
            for goal_type, analysis in goal_analysis['achievements'].items():
                if isinstance(analysis, dict) and 'achieved' in analysis:
                    achievements[goal_type] = analysis['achieved']
        
        return achievements
