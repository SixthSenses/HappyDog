# 몸무게 월간 분석 API 가이드

**엔드포인트**: `GET /api/pet-care/{pet_id}/weight/monthly-analysis`  
**인증**: Bearer Token 필요  
**날짜**: 2025-10-18

---

## 📋 개요

6개월간의 월별 평균 몸무게 데이터와 비교 분석 텍스트를 제공하는 API입니다.

### 핵심 특징
- ✅ **항상 오늘 기준**: 과거 데이터를 조회하더라도 기준 시점은 오늘
- ✅ **월별 평균**: 각 월의 모든 몸무게 기록의 평균값
- ✅ **자동 분석 텍스트**: 6개월 전과의 비교 결과를 사람이 읽기 쉬운 문장으로 제공

---

## 🔗 엔드포인트

```http
GET /api/pet-care/{pet_id}/weight/monthly-analysis
Authorization: Bearer {access_token}
```

### Path Parameters
- `pet_id` (string, required): 반려동물 ID

---

## 📤 응답 구조

### 성공 응답 (200 OK)

```json
{
  "analysis": {
    "title": "몸무게가 비슷해요",
    "description": "6개월 전보다 0.5kg 차이나요",
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
    {
      "year_month": "2025-07",
      "label": "7월",
      "average_weight": 33.3,
      "record_count": 18
    },
    {
      "year_month": "2025-08",
      "label": "8월",
      "average_weight": 33.5,
      "record_count": 22
    },
    {
      "year_month": "2025-09",
      "label": "9월",
      "average_weight": 33.7,
      "record_count": 19
    },
    {
      "year_month": "2025-10",
      "label": "10월",
      "average_weight": 35.6,
      "record_count": 12
    }
  ],
  "meta": {
    "reference_date": "2025-10-18",
    "timezone": "Asia/Seoul"
  }
}
```

### 응답 필드 설명

#### `analysis` (object)
분석 결과 및 비교 텍스트

| 필드 | 타입 | 설명 |
|------|------|------|
| `title` | string | 메인 분석 텍스트 ("몸무게가 비슷해요" / "몸무게가 늘었어요" / "몸무게가 줄었어요") |
| `description` | string | 상세 설명 (차이값 포함) |
| `current_month_avg` | float or null | 현재 월 평균 몸무게 (kg) |
| `six_months_ago_avg` | float or null | 6개월 전 월 평균 몸무게 (kg) |
| `difference` | float or null | 차이 (현재 - 6개월 전, kg) |

#### `monthly_data` (array)
월별 몸무게 데이터 (최근 6개월, 오래된 순)

| 필드 | 타입 | 설명 |
|------|------|------|
| `year_month` | string | 연월 ('YYYY-MM') |
| `label` | string | 월 라벨 ('5월', '6월', ...) |
| `average_weight` | float or null | 해당 월 평균 몸무게 (kg) |
| `record_count` | integer | 해당 월 기록 개수 |

#### `meta` (object)
메타 정보

| 필드 | 타입 | 설명 |
|------|------|------|
| `reference_date` | string | 기준 날짜 (YYYY-MM-DD, 항상 오늘) |
| `timezone` | string | 타임존 ('Asia/Seoul') |

---

## 📊 분석 텍스트 규칙

### 타이틀 결정 기준
- 차이 ≤ 1.5kg: **"몸무게가 비슷해요"**
- 차이 > 1.5kg: **"몸무게가 늘었어요"**
- 차이 < -1.5kg: **"몸무게가 줄었어요"**

### 데이터 부족 시
```json
{
  "analysis": {
    "title": "몸무게 데이터가 부족해요",
    "description": "6개월 동안 매월 한 번 이상 기록하면 분석을 볼 수 있어요",
    "current_month_avg": null,
    "six_months_ago_avg": null,
    "difference": null
  }
}
```

---

## 💡 사용 예시

### 예시 1: 정상적인 데이터가 있는 경우

**요청**:
```bash
curl -X GET \
  'https://api.happydog.com/api/pet-care/abc123/weight/monthly-analysis' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIs...'
```

**응답** (몸무게가 늘었을 때):
```json
{
  "analysis": {
    "title": "몸무게가 늘었어요",
    "description": "6개월 전보다 2.8kg 늘었어요",
    "current_month_avg": 35.6,
    "six_months_ago_avg": 32.8,
    "difference": 2.8
  },
  "monthly_data": [
    {"year_month": "2025-05", "label": "5월", "average_weight": 32.8, "record_count": 15},
    {"year_month": "2025-06", "label": "6월", "average_weight": 33.1, "record_count": 20},
    {"year_month": "2025-07", "label": "7월", "average_weight": 33.3, "record_count": 18},
    {"year_month": "2025-08", "label": "8월", "average_weight": 33.5, "record_count": 22},
    {"year_month": "2025-09", "label": "9월", "average_weight": 33.7, "record_count": 19},
    {"year_month": "2025-10", "label": "10월", "average_weight": 35.6, "record_count": 12}
  ],
  "meta": {
    "reference_date": "2025-10-18",
    "timezone": "Asia/Seoul"
  }
}
```

### 예시 2: 일부 월에 데이터가 없는 경우

**응답**:
```json
{
  "analysis": {
    "title": "몸무게가 비슷해요",
    "description": "6개월 전보다 0.3kg 차이나요",
    "current_month_avg": 33.5,
    "six_months_ago_avg": 33.2,
    "difference": 0.3
  },
  "monthly_data": [
    {"year_month": "2025-05", "label": "5월", "average_weight": 33.2, "record_count": 5},
    {"year_month": "2025-06", "label": "6월", "average_weight": null, "record_count": 0},
    {"year_month": "2025-07", "label": "7월", "average_weight": 33.0, "record_count": 8},
    {"year_month": "2025-08", "label": "8월", "average_weight": null, "record_count": 0},
    {"year_month": "2025-09", "label": "9월", "average_weight": 33.3, "record_count": 10},
    {"year_month": "2025-10", "label": "10월", "average_weight": 33.5, "record_count": 7}
  ]
}
```

### 예시 3: 현재 월 또는 6개월 전 월에 데이터가 없는 경우

**응답**:
```json
{
  "analysis": {
    "title": "몸무게 데이터가 부족해요",
    "description": "6개월 동안 매월 한 번 이상 기록하면 분석을 볼 수 있어요",
    "current_month_avg": null,
    "six_months_ago_avg": 32.5,
    "difference": null
  },
  "monthly_data": [
    {"year_month": "2025-05", "label": "5월", "average_weight": 32.5, "record_count": 12},
    {"year_month": "2025-06", "label": "6월", "average_weight": 32.8, "record_count": 15},
    {"year_month": "2025-07", "label": "7월", "average_weight": 33.0, "record_count": 18},
    {"year_month": "2025-08", "label": "8월", "average_weight": 33.2, "record_count": 14},
    {"year_month": "2025-09", "label": "9월", "average_weight": 33.5, "record_count": 20},
    {"year_month": "2025-10", "label": "10월", "average_weight": null, "record_count": 0}
  ]
}
```

---

## 🎨 UI 구현 가이드

### Figma 디자인 매핑 (node-id: 3354-15219)

#### 타이틀 섹션
```dart
Text(
  '몸무게',
  style: TextStyle(color: Colors.blue, fontSize: 14),
)
Text(
  response['analysis']['title'],  // "2025년 9월 21일은 오늘보다 무거웠어요"
  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
)
```

#### 차트 섹션
```dart
// 6개월 차트 표시
BarChart(
  data: response['monthly_data'].map((month) => {
    'label': month['label'],  // "5월", "6월", ...
    'value': month['average_weight'] ?? 0,  // null인 경우 0 처리
  }).toList(),
  highlightCurrent: true,  // 현재 월 하이라이트
)
```

#### 월간 분석 텍스트
```dart
Container(
  padding: EdgeInsets.all(16),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        '월간 분석',
        style: TextStyle(fontSize: 14, color: Colors.grey),
      ),
      SizedBox(height: 8),
      Text(
        response['analysis']['title'],  // "6개월 전 보다 몸무게가 늘었어요"
        style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
      ),
    ],
  ),
)
```

---

## 🔍 주의사항

### 1. 항상 오늘 기준
- **중요**: 이 API는 항상 오늘을 기준으로 최근 6개월 데이터를 반환합니다.
- 과거 특정 날짜의 분석을 보려면 별도 API가 필요합니다.
- `meta.reference_date`는 항상 오늘 날짜입니다.

### 2. 월별 평균 계산
- 각 월의 **모든 몸무게 기록**의 평균값을 사용합니다.
- 하루에 여러 번 기록해도 모두 평균 계산에 포함됩니다.
- 기록이 없는 월은 `average_weight: null`로 반환됩니다.

### 3. 비교 기준
- **현재 월 평균** vs **6개월 전 월 평균** 비교
- 예: 2025년 10월 기준 → 2025년 10월 vs 2025년 4월
- 둘 중 하나라도 데이터가 없으면 "데이터가 부족해요" 표시

### 4. 데이터 일관성
- 6개월간의 데이터는 항상 배열 형태로 반환됩니다 (6개 요소).
- 기록이 없는 월도 포함되며, `average_weight: null`로 표시됩니다.
- `record_count: 0`인 경우 해당 월에 기록이 없음을 의미합니다.

---

## 🚨 에러 응답

### 400 Bad Request
잘못된 요청 (발생 가능성 낮음, 쿼리 파라미터 없음)

### 401 Unauthorized
인증 토큰이 없거나 유효하지 않음

### 403 Forbidden
해당 반려동물에 대한 접근 권한 없음

### 404 Not Found
반려동물을 찾을 수 없음

### 500 Internal Server Error
서버 오류

---

## 📚 관련 API
- `GET /api/pet-care/{pet_id}/records/summary/range`: 기간별 상세 기록 조회
- `POST /api/pet-care/{pet_id}/records`: 몸무게 기록 생성
- `GET /api/pet-care/{pet_id}/records/daily/summary`: 일별 요약 조회

---

**작성일**: 2025-10-18  
**버전**: 1.0.0  
**상태**: ✅ 구현 완료
