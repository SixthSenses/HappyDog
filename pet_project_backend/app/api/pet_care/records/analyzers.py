from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from app.utils.datetime_utils import DateTimeUtils

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
        
        # 식사 목표: 목표값이 설정되어 있으면 기록 유무와 관계없이 항상 반환
        if isinstance(meal_goal, int) and meal_goal > 0:
            actual_meal = meal_count if isinstance(meal_count, int) else 0
            achievements['meal'] = {
                'actual': actual_meal,
                'goal': meal_goal,
                'percentage': round(actual_meal / meal_goal * 100, 1),
                'achieved': actual_meal >= meal_goal,
            }
        
        # 활동 목표: 목표값이 설정되어 있으면 기록 유무와 관계없이 항상 반환
        if isinstance(act_goal, int) and act_goal > 0:
            actual_activity = activity_minutes if isinstance(activity_minutes, int) else 0
            achievements['activity'] = {
                'actual': actual_activity,
                'goal': act_goal,
                'percentage': round(actual_activity / act_goal * 100, 1),
                'achieved': actual_activity >= act_goal,
                'detail': {
                    'sessions': sessions,
                    'minutes_per_session': per_session,
                    'derived_goal_minutes': derived_minutes or act_goal,
                }
            }
        
        # 체중 목표: 목표값이 설정되어 있으면 항상 반환 (UI에서 목표 표시용)
        if isinstance(tgt_weight, (int, float)):
            if isinstance(weight, (int, float)):
                # 실제 측정값이 있는 경우: 차이와 달성 여부 계산
                diff = weight - float(tgt_weight)
                achievements['weight'] = {
                    'actual': weight,
                    'goal': float(tgt_weight),
                    'at_goal': abs(diff) <= 0.1,
                    'diff': round(diff, 2),
                }
            else:
                # 측정값이 없는 경우: 목표만 반환 (actual은 null)
                achievements['weight'] = {
                    'actual': None,
                    'goal': float(tgt_weight),
                    'at_goal': None,
                    'diff': None,
                }

        return {
            'date': date,
            'achievements': achievements,
        }

    def analyze_range_with_history(
        self,
        grouped: Dict[str, List[Dict[str, Any]]],
        settings_by_effective_date: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze achievements using the settings in effect for each day."""
        days = sorted(grouped.keys())
        counts = {'meal': 0, 'activity': 0, 'weight': 0}
        achievement_dates = {'meal': [], 'activity': [], 'weight': []}

        if not settings_by_effective_date:
            logger.warning("analyze_range_with_history called without settings map")
            return {
                'days_achieved': counts,
                'achievement_dates': achievement_dates,
                'achievement_rates': {k: 0.0 for k in counts},
            }

        sorted_effective_dates = sorted(settings_by_effective_date.keys())
        active_settings: Optional[Dict[str, Any]] = None
        idx = 0

        for date_key in days:
            while idx < len(sorted_effective_dates) and sorted_effective_dates[idx] <= date_key:
                active_settings = settings_by_effective_date[sorted_effective_dates[idx]]
                idx += 1

            if active_settings is None:
                active_settings = settings_by_effective_date[sorted_effective_dates[0]]

            rows = grouped[date_key]
            daily = self.analyze_daily(rows, date_key, active_settings)
            achievements = daily.get('achievements', {})

            if achievements.get('meal', {}).get('achieved'):
                counts['meal'] += 1
                achievement_dates['meal'].append(date_key)

            if achievements.get('activity', {}).get('achieved'):
                counts['activity'] += 1
                achievement_dates['activity'].append(date_key)

            if achievements.get('weight', {}).get('at_goal'):
                counts['weight'] += 1
                achievement_dates['weight'].append(date_key)

        total_days = len(days) or 1
        achievement_rates = {k: round(v / total_days * 100, 1) for k, v in counts.items()}

        logger.debug(
            "Range analysis with history computed",
            extra={'days_achieved': counts, 'total_days': total_days},
        )

        return {
            'days_achieved': counts,
            'achievement_dates': achievement_dates,
            'achievement_rates': achievement_rates,
        }

    def analyze_range(self, grouped: Dict[str, List[Dict[str, Any]]], settings: Dict[str, Any]) -> Dict[str, Any]:
        """Backward-compatible wrapper for legacy single-setting analysis."""
        base_date = min(grouped.keys()) if grouped else DateTimeUtils.today_kst_as_date_str()
        settings_map = {base_date: settings}
        return self.analyze_range_with_history(grouped, settings_map)

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


class WeightMonthlyAnalyzer:
    """월별 몸무게 분석을 담당하는 클래스 (6개월 평균 및 비교 텍스트 생성)"""

    @staticmethod
    def calculate_monthly_averages(
        records_by_date: Dict[str, List[Dict[str, Any]]],
        target_months: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        월별 평균 몸무게를 계산합니다.
        
        Args:
            records_by_date: 날짜별 기록 딕셔너리 {'YYYY-MM-DD': [records]}
            target_months: 계산할 월 리스트 ['YYYY-MM', ...]
            
        Returns:
            dict: {
                'YYYY-MM': {
                    'average_weight': float,
                    'record_count': int,
                    'weights': [float, ...]  # 디버깅용
                }
            }
        """
        monthly_weights: Dict[str, List[float]] = {month: [] for month in target_months}
        
        for date_str, records in records_by_date.items():
            year_month = date_str[:7]  # 'YYYY-MM-DD' -> 'YYYY-MM'
            
            if year_month not in monthly_weights:
                continue
            
            # 해당 날짜의 몸무게 기록 추출 (마지막 값)
            for record in records:
                if record.get('record_type') == 'weight':
                    weight = record.get('data')
                    if weight is not None:
                        try:
                            monthly_weights[year_month].append(float(weight))
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid weight value at {date_str}: {weight}")
        
        # 월별 평균 계산
        result = {}
        for month in target_months:
            weights = monthly_weights[month]
            if weights:
                result[month] = {
                    'average_weight': sum(weights) / len(weights),
                    'record_count': len(weights),
                    'weights': weights  # 디버깅용
                }
            else:
                result[month] = {
                    'average_weight': None,
                    'record_count': 0,
                    'weights': []
                }
        
        return result

    @staticmethod
    def generate_analysis_text(
        current_avg: Optional[float],
        six_months_ago_avg: Optional[float]
    ) -> Dict[str, Any]:
        """
        현재 월과 6개월 전 월의 평균 몸무게를 비교하여 분석 텍스트를 생성합니다.
        
        기준:
        - 차이 ≤ 1.5kg: "몸무게가 비슷해요"
        - 차이 > 1.5kg: "몸무게가 늘었어요"
        - 차이 < -1.5kg: "몸무게가 줄었어요"
        
        Args:
            current_avg: 현재 월 평균 몸무게
            six_months_ago_avg: 6개월 전 월 평균 몸무게
            
        Returns:
            dict: {
                'title': str,  # 메인 텍스트
                'description': str,  # 상세 설명
                'current_month_avg': float or None,
                'six_months_ago_avg': float or None,
                'difference': float or None
            }
        """
        if current_avg is None or six_months_ago_avg is None:
            return {
                'title': '몸무게 데이터가 부족해요',
                'description': '6개월 동안 매월 한 번 이상 기록하면 분석을 볼 수 있어요',
                'current_month_avg': current_avg,
                'six_months_ago_avg': six_months_ago_avg,
                'difference': None
            }
        
        difference = current_avg - six_months_ago_avg
        abs_diff = abs(difference)
        
        # 타이틀 결정
        if abs_diff <= 1.5:
            title = "몸무게가 비슷해요"
        elif difference > 1.5:
            title = "몸무게가 늘었어요"
        else:
            title = "몸무게가 줄었어요"
        
        # 상세 설명 생성
        if abs_diff <= 1.5:
            description = f"6개월 전보다 {abs_diff:.1f}kg 차이나요"
        elif difference > 0:
            description = f"6개월 전보다 {abs_diff:.1f}kg 늘었어요"
        else:
            description = f"6개월 전보다 {abs_diff:.1f}kg 줄었어요"
        
        return {
            'title': title,
            'description': description,
            'current_month_avg': round(current_avg, 2),
            'six_months_ago_avg': round(six_months_ago_avg, 2),
            'difference': round(difference, 2)
        }
