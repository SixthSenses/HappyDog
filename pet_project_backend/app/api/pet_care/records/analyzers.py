from __future__ import annotations
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class GoalAnalyzer:
    """Compute goal progress for day/range.

    settings keys expected (normalized):
      - goalMealCount
      - goalActivityMinutes
      - goalWeight (optional)
    """

    def analyze_daily(self, rows: List[Dict[str, Any]], date: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        meal_count = self._extract_last(rows, 'meal_count')
        activity_minutes = self._extract_total(rows, 'activity')
        weight = self._extract_last(rows, 'weight')
        
        # Debug logging
        logger.debug(f"GoalAnalyzer.analyze_daily for {date}: meal_count={meal_count}, "
                    f"activity_minutes={activity_minutes}, weight={weight}, "
                    f"total_records={len(rows)}")

        meal_goal = settings.get('goalMealCount')
        # 활동 목표: 세션 × 분이 있으면 이를 우선 사용, 없으면 분 목표 사용
        sessions = settings.get('goalActivitySessions') or 0
        per_session = settings.get('activitySessionMinutes') or 0
        derived_minutes = sessions * per_session if sessions and per_session else None
        act_goal = derived_minutes if isinstance(derived_minutes, int) and derived_minutes > 0 else settings.get('goalActivityMinutes')
        tgt_weight = settings.get('goalWeight')

        achievements: Dict[str, Any] = {}
        if isinstance(meal_goal, int) and meal_goal > 0 and isinstance(meal_count, int):
            achievements['meal'] = {
                'actual': meal_count,
                'goal': meal_goal,
                'percentage': round(meal_count / meal_goal * 100, 1),
                'achieved': meal_count >= meal_goal,
            }
        if isinstance(act_goal, int) and act_goal > 0 and isinstance(activity_minutes, int):
            achievements['activity'] = {
                'actual': activity_minutes,
                'goal': act_goal,
                'percentage': round(activity_minutes / act_goal * 100, 1),
                'achieved': activity_minutes >= act_goal,
                'detail': {
                    'sessions': sessions,
                    'minutes_per_session': per_session,
                    'derived_goal_minutes': derived_minutes or act_goal,
                }
            }
        if isinstance(tgt_weight, (int, float)) and isinstance(weight, (int, float)):
            diff = weight - float(tgt_weight)
            achievements['weight'] = {
                'actual': weight,
                'goal': float(tgt_weight),
                'at_goal': abs(diff) <= 0.1,
                'diff': round(diff, 2),
            }

        return {
            'date': date,
            'achievements': achievements,
        }

    def analyze_range(self, grouped: Dict[str, List[Dict[str, Any]]], settings: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze goal achievements across a date range.
        
        Returns:
            dict: Contains achievement counts, dates, and rates
                - days_achieved: {goal_type: count}
                - achievement_dates: {goal_type: [date1, date2, ...]}
                - achievement_rates: {goal_type: percentage}
        """
        days = sorted(grouped.keys())
        counts = {'meal': 0, 'activity': 0, 'weight': 0}
        achievement_dates = {'meal': [], 'activity': [], 'weight': []}
        
        for d in days:
            rows = grouped[d]
            daily = self.analyze_daily(rows, d, settings)
            ach = daily.get('achievements', {})
            
            # Meal goal achieved
            if ach.get('meal', {}).get('achieved'):
                counts['meal'] += 1
                achievement_dates['meal'].append(d)
            
            # Activity goal achieved
            if ach.get('activity', {}).get('achieved'):
                counts['activity'] += 1
                achievement_dates['activity'].append(d)
            
            # Weight goal achieved
            if ach.get('weight', {}).get('at_goal'):
                counts['weight'] += 1
                achievement_dates['weight'].append(d)
        
        total = len(days) or 1
        rates = {k: round(v / total * 100, 1) for k, v in counts.items()}
        
        logger.debug(f"Range analysis: days_achieved={counts}, achievement_dates={achievement_dates}")
        
        return {
            'days_achieved': counts,
            'achievement_dates': achievement_dates,
            'achievement_rates': rates
        }

    @staticmethod
    def _extract_last(rows: List[Dict[str, Any]], rtype: str):
        """Extract the last (most recent) value for a given record type.
        
        Used for cumulative counts (meal_count) and single measurements (weight, bcs).
        """
        filtered = [r for r in rows if r.get('record_type') == rtype]
        return filtered[-1].get('data') if filtered else None

    @staticmethod
    def _extract_total(rows: List[Dict[str, Any]], rtype: str):
        """Calculate total sum for a given record type.
        
        Used for activity minutes where multiple sessions should be added together.
        Safely handles None and invalid values.
        
        Returns:
            int or None: Total sum if any valid records found, None otherwise
        """
        total = 0
        found = False
        for r in rows:
            if r.get('record_type') == rtype:
                val = r.get('data')
                if val is not None:
                    try:
                        total += int(val)
                        found = True
                    except (ValueError, TypeError):
                        # Skip invalid values
                        continue
        return total if found else None


class TrendAnalyzer:
    def build_trends(self, grouped: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        weight_trend = []
        meal_trend = []
        activity_trend = []
        for date in sorted(grouped.keys()):
            rows = grouped[date]
            weight = GoalAnalyzer._extract_last(rows, 'weight')
            meal = GoalAnalyzer._extract_last(rows, 'meal_count')
            activity = GoalAnalyzer._extract_total(rows, 'activity')
            if weight is not None:
                weight_trend.append({'date': date, 'weight': weight})
            if meal is not None:
                meal_trend.append({'date': date, 'meal_count': meal})
            if activity:
                activity_trend.append({'date': date, 'activity_minutes': activity})
        return {
            'weight_trend': weight_trend,
            'meal_frequency_trend': meal_trend,
            'activity_trend': activity_trend,
        }


class MonthlyMessageBuilder:
    """Builds human-friendly monthly text based on common conventions."""

    @staticmethod
    def build(encouragement_count: int) -> str:
        if encouragement_count >= 20:
            return "정말 대단해요!"
        if encouragement_count >= 10:
            return "아주 잘하고 있어요!"
        if encouragement_count >= 5:
            return "꾸준함이 보여요!"
        if encouragement_count >= 1:
            return "좋은 시작이에요!"
        return "이번 달엔 지금부터 시작해볼까요?"
