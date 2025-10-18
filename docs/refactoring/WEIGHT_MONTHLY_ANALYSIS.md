# 몸무게 월간 분석 엔드포인트 구현

**날짜**: 2025-10-18  
**요구사항**: Figma 디자인 (node-id: 3354-15219, 3430-15517)  
**목적**: 6개월 몸무게 월별 평균 및 분석 텍스트 제공

---

## 🎯 요구사항 정리

### 데이터 표시
- **6개월 데이터**: 현재 월 포함 최근 6개월
- **월별 평균**: 각 월의 모든 몸무게 기록의 평균값
- **기준 시점**: 항상 오늘 기준 (과거 데이터 조회해도 동일)

### 분석 텍스트
- **현재 월 vs 6개월 전 월** 비교
- 차이 ≤ 1.5kg: "몸무게가 비슷해요"
- 차이 > 1.5kg: "몸무게가 늘었어요"
- 차이 < -1.5kg: "몸무게가 줄었어요"

### 예시 (2025년 10월 기준)
```
현재: 2025-10-18
6개월 데이터: 2025-05 ~ 2025-10
비교: 2025-10 평균 vs 2025-04 평균 (6개월 전)
```

---

## 📝 구현 계획

### 1. 새로운 엔드포인트
```
GET /api/pet-care/{pet_id}/weight/monthly-analysis
```

### 2. 응답 구조
```json
{
  "analysis": {
    "title": "몸무게가 비슷해요",
    "description": "6개월 전보다 0.5kg 늘었어요",
    "current_month_avg": 33.5,
    "six_months_ago_avg": 33.0,
    "difference": 0.5
  },
  "monthly_data": [
    {
      "year_month": "2025-05",
      "label": "5월",
      "average_weight": 32.8,
      "record_count": 15
    },
    {
      "year_month": "2025-06",
      "label": "6월",
      "average_weight": 33.1,
      "record_count": 20
    },
    // ... 총 6개월
  ],
  "meta": {
    "reference_date": "2025-10-18",
    "timezone": "Asia/Seoul"
  }
}
```

### 3. 구현 파일
- **라우트**: `app/api/pet_care/records/routes.py`
- **서비스**: `app/api/pet_care/records/record_integration_service.py` (새 메서드)
- **분석 로직**: `app/api/pet_care/records/analyzers.py` (새 클래스)
- **스키마**: `app/api/pet_care/records/schemas.py`

---

## 🔧 구현 상세

### Analyzer (analyzers.py)
```python
class WeightMonthlyAnalyzer:
    """월별 몸무게 분석을 담당하는 클래스"""
    
    @staticmethod
    def calculate_monthly_averages(
        records: Dict[str, List[Dict[str, Any]]],
        months: int = 6
    ) -> List[Dict[str, Any]]:
        """월별 평균 몸무게 계산"""
        pass
    
    @staticmethod
    def generate_analysis_text(
        current_avg: Optional[float],
        six_months_ago_avg: Optional[float]
    ) -> Dict[str, Any]:
        """분석 텍스트 생성"""
        pass
```

### Integration Service (record_integration_service.py)
```python
def get_weight_monthly_analysis(self, pet_id: str) -> Dict[str, Any]:
    """6개월 몸무게 월간 분석"""
    pass
```

### Route (routes.py)
```python
@pet_care_records_bp.route('/<string:pet_id>/weight/monthly-analysis', methods=['GET'])
@jwt_required()
def get_weight_monthly_analysis(pet_id: str):
    """몸무게 월간 분석 조회"""
    pass
```

---

## ✅ 구현 시작
