# breeds API

품종(breeds) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| GET | /api/breeds/ | optional | 품종 목록/요약 목록 조회 (limit/offset/summary) | 200, 400, 500 |
| GET | /api/breeds/{breed_name} | optional | 특정 품종 단건 조회 | 200, 404, 500 |
| GET | /api/breeds/search | optional | 부분 문자열 검색(클라 필터) | 200, 400, 500 |
| GET | /api/breeds/exists/{breed_name} | optional | 해당 품종 존재 여부 확인 | 200, 500 |

## 스키마/데이터 형식

| 스키마 | 필드 | 타입 | 비고 |
|---|---|---|---|
| Breed | breed_name | string |  |
|  | life_expectancy | float(0~30) |  |
|  | height_cm | object{male: float, female: float} |  |
|  | weight_kg | object{male: float, female: float} |  |
|  | created_at/updated_at | ISO8601 | optional |
| BreedList | breeds | array<Breed> |  |
|  | total_count | int |  |
| SummaryList | breed_name | string |  |
|  | life_expectancy | float |  |

## 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| GET / | 400 INVALID_PARAMETER | 잘못된 쿼리 |
|  | 500 BREED_FETCH_FAILED | 서버 오류 |
| GET /{name} | 404 BREED_NOT_FOUND | 미존재 |
|  | 500 BREED_FETCH_FAILED | 서버 오류 |
| GET /search | 400 MISSING_PARAMETER/INVALID_PARAMETER | 파라미터 오류 |
|  | 500 BREED_SEARCH_FAILED | 서버 오류 |
| GET /exists/{name} | 500 BREED_CHECK_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 400 | INVALID_PARAMETER | 유효하지 않은 파라미터입니다. |
| 400 | MISSING_PARAMETER | 필수 파라미터가 누락되었습니다. |
| 404 | BREED_NOT_FOUND | 요청한 품종을 찾을 수 없습니다. |
| 500 | BREED_FETCH_FAILED/BREED_SEARCH_FAILED/BREED_CHECK_FAILED | 품종 정보를 조회하는 중 오류가 발생했습니다. |

## 저장/조회 로직

| 항목 | 내용 |
|---|---|
| 컬렉션 | breeds (doc ID=breed_name) |
| 목록 | order_by('breed_name'), offset은 start_after |
| 검색 | 전체 로드 후 파이썬 부분 문자열 필터(대소문자 무시) |
| 통계 | (제거됨) |
