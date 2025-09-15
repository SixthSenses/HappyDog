## breeds API

실제 코드(app/api/breeds/*) 기준의 품종(breeds) 도메인 문서입니다. swagger 자동 생성 산출물의 예시는 제거/무시했습니다.

---
### 1. 엔드포인트 개요
| Method | Path | Auth | 설명 | 주요 파라미터 |
|--------|------|------|------|---------------|
| GET | /api/breeds/ | optional | 품종 목록 조회 (전체 또는 요약) | limit, offset, summary |
| GET | /api/breeds/{breed_name} | optional | 특정 품종 상세 | breed_name (URL encoded) |
| GET | /api/breeds/search | optional | 부분 문자열 검색 (in-memory filter) | q, limit, offset |
| GET | /api/breeds/exists/{breed_name} | optional | 품종 존재 여부 확인 | breed_name |

요약 조회(summary=true)는 height/weight 전체 대신 요약 스키마(이름 + 기대수명)만 반환.

---
### 2. 요청 파라미터 세부
1) GET /api/breeds/
 - limit (int, optional): 양수. 미지정 시 전체(서비스는 제한 없음)
 - offset (int, optional, 기본 0): 0 이상. Firestore start_after 전략 (대량 시 비효율 가능)
 - summary (bool, optional, 기본 false): 'true' 문자열이면 요약 모드

2) GET /api/breeds/{breed_name}
 - path 변수 URL 디코딩 후 사용 (한글 지원)

3) GET /api/breeds/search
 - q (string, required): 1~100자 (현재 Firestore 문서 ID가 '한국어 품종명' 이므로 반드시 한국어 품종명(또는 그 부분 문자열)을 사용해야 매칭됨. 예: "하페이루", "리트리버")
 - limit (int, optional, 기본 50): 1~100
 - offset (int, optional, 기본 0): 0 이상

4) GET /api/breeds/exists/{breed_name}
 - 단순 존재 여부 체크

---
### 3. 응답 스키마 (실제 marshmallow 정의 기준)

공통 필드 타입 요약:
| 이름 | 타입 | 설명 |
|------|------|------|
| breed_name | string | Firestore 문서 ID (=품종명). 현재 저장 값은 표준화된 '한국어 품종명' 이며 영어 slug 미사용. (예: "하페이루 두 알렌테주") |
| life_expectancy | float (0~30) | 기대 수명 (년) |
| height_cm | object | { male: float>=0, female: float>=0 } |
| weight_kg | object | { male: float>=0, female: float>=0 } |
| created_at / updated_at | ISO8601 string (dump only) | 선택적 저장 메타 |

1) 목록 (summary=false)
```json
{
	"breeds": [ {
		 "breed_name": "golden_retriever",
		 "life_expectancy": 12.0,
		 "height_cm": {"male": 60.0, "female": 55.0},
		 "weight_kg": {"male": 32.0, "female": 28.0},
		 "created_at": "2025-01-10T12:00:00Z",
		 "updated_at": "2025-06-01T08:30:00Z"
	}],
	"total_count": 150
}
```

2) 목록 (summary=true)
```json
{
	"breeds": [ {"breed_name": "golden_retriever", "life_expectancy": 12.0} ],
	"total_count": 150
}
```

3) 단건 상세 (영문 예시 - 구형 데이터 혹은 내부 테스트용일 수 있음)
```json
{
	"breed_name": "golden_retriever",
	"life_expectancy": 12.0,
	"height_cm": {"male": 60.0, "female": 55.0},
	"weight_kg": {"male": 32.0, "female": 28.0},
	"created_at": "2025-01-10T12:00:00Z",
	"updated_at": "2025-06-01T08:30:00Z"
}
```

3-1) 단건 상세 (실제 운영 한국어 예시)
```json
{
	"breed_name": "하페이루 두 알렌테주",
	"life_expectancy": 13.0,
	"height_cm": {"male": 68.6, "female": 58.3},
	"weight_kg": {"male": 47.4, "female": 40.3},
	"created_at": "2025-08-20T07:47:50.799255+00:00",
	"updated_at": "2025-08-20T07:47:50.799255+00:00"
}
```

4) 검색 결과 (한국어 부분 문자열 검색 예시)
```json
{
	"breeds": [
		{"breed_name": "golden_retriever", "life_expectancy": 12.0, "height_cm": {"male": 60.0, "female": 55.0}, "weight_kg": {"male": 32.0, "female": 28.0}},
		{"breed_name": "labrador_retriever", "life_expectancy": 13.0, "height_cm": {"male": 61.0, "female": 56.0}, "weight_kg": {"male": 31.0, "female": 27.0}}
	],
	"total_count": 2
}
```

실제 운영 저장 구조에서는 두 예시가 각각 "골든 리트리버", "라브라도 리트리버" 와 같이 한국어로 저장/반환됩니다. 위 영문 표기는 과거/테스트 데이터 참고용입니다.

5) 존재 여부
```json
{"breed_name": "golden_retriever", "exists": true}
```

---
### 4. 에러 코드 (실제 routes.py 반환 기준)

| error_code | HTTP | 발생 조건 |
|------------|------|-----------|
| INVALID_PARAMETER | 400 | offset<0, limit<=0 (목록) / query 길이 초과 / limit 범위 위반 / offset 범위 위반 |
| MISSING_PARAMETER | 400 | 검색 q 누락 |
| BREED_NOT_FOUND | 404 | 단건 조회 시 품종 없음 |
| BREED_FETCH_FAILED | 500 | 목록/단건 조회 예외 발생 |
| BREED_SEARCH_FAILED | 500 | 검색 처리 예외 발생 |
| BREED_CHECK_FAILED | 500 | 존재 여부 확인 중 예외 |
| VALIDATION_ERROR | 400 | (마시멜로 ValidationError 핸들러) 스키마 검증 실패 시 |
| NOT_FOUND | 404 | 블루프린트 내 미정의 라우트 접근 |
| INTERNAL_SERVER_ERROR | 500 | 블루프린트 errorhandler(500) 트리거 시 |

주의: @error_responses 데코레이터에 선언된 CommonErrors.* 는 실제 반환 JSON과 코드가 약간 다를 수 있으므로(예: INTERNAL_ERROR vs BREED_FETCH_FAILED) 클라이언트 파싱은 위 표 우선.

샘플 에러 응답:
```json
{ "error_code": "INVALID_PARAMETER", "message": "offset은 0 이상이어야 합니다." }
```

---
### 5. 동작/구현 세부
| 항목 | 내용 |
|------|------|
| 저장소 | Firestore collection "breeds" (doc ID = breed_name) |
| 목록 쿼리 | order_by('breed_name'), offset 은 start_after 로 시뮬레이션 (대량 데이터 시 비용 증가) |
| 검색 | 전체 로드 후 파이썬 in-memory 부분 문자열(lower) 필터 (한국어 breed_name 기준) -> (확장 시 인덱싱/전용 검색 서비스 고려) |
| 요약 | life_expectancy 만 포함한 경량 구조 (height/weight 제외) |
| 무결성 | height_cm / weight_kg 각 key(male,female)는 0 이상 float; 없을 경우 문서 자체 정합성 이슈 가능 |
| 확장 가능성 | temperament, origin 등 swagger 예시 필드는 현재 저장/반환되지 않음 (추가 시 스키마 갱신 필요) |

성능 주의: search 는 모든 품종을 메모리로 가져온 뒤 필터링하므로 품종 개수가 커지면 (O(N)) 응답 지연 및 비용 증가. 캐싱 또는 prefix 인덱스 도입 고려.

---
### 6. 사용 예시 (curl)
목록:
```bash
curl -X GET "https://api.example.com/api/breeds/?limit=20&offset=0"
```
요약 목록:
```bash
curl -X GET "https://api.example.com/api/breeds/?summary=true&limit=50"
```
단건:
```bash
curl -X GET "https://api.example.com/api/breeds/%ED%95%98%ED%8E%98%EC%9D%B4%EB%A3%A8%20%EB%91%90%20%EC%95%8C%EB%A0%8C%ED%85%8C%EC%A3%BC"  # "하페이루 두 알렌테주"
```
검색:
```bash
curl -X GET "https://api.example.com/api/breeds/search?q=%EB%A6%AC%ED%8A%B8%EB%A6%AC%EB%B2%84&limit=10"  # "리트리버" 부분 검색
```
존재 여부:
```bash
curl -X GET "https://api.example.com/api/breeds/exists/%EA%B3%A8%EB%93%A0%20%EB%A6%AC%ED%8A%B8%EB%A6%AC%EB%B2%84"  # "골든 리트리버" 존재 여부
```

---
### 7. 클라이언트 구현 팁
| 상황 | 권장 처리 |
|------|-----------|
| summary=true 목록 | 드롭다운/오토컴플리트 초기 로드에 사용 (가벼움) |
| 검색(q) | debounce (300~400ms) + 로컬 캐시로 중복 호출 최소화 |
| 에러 파싱 | error_code 우선 switch; 미정의 시 HTTP status fallback |
| 빈 결과 | breeds=[], total_count=0 정상 처리 |

---
### 8. 향후 개선 후보 (문서용)
1) 검색: 전처리된 trigram / prefix 인덱스로 Firestore 호출 수 감소
2) 목록: count 질의 최적화 (현재 전체 stream 후 count → 비용) / Cloud Function 캐시
3) 국제화: breed_name 외 display_name_ko 등 분리
4) temperament / origin 등 확장 시 버전 필드 추가 고려

---
Last Updated: 2025-09-11 (한국어 breed_name 반영)
