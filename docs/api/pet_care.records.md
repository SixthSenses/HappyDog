# pet_care/records API (Code-first, swagger 무시)

펫 케어 기록 관리 도메인. 단일 기록 CRUD + 일/범위 요약 + 목표(progress) 분석 & 달성 알림 트리거.

## 최근 변경 사항
| 변경 | 내용 |
|---|---|
| timestamp 일관화 | 응답 `timestamp` = ms 정수 (직렬화 충돌 방지), `timestamp_ms` 동일 값 중복 제공 (레거시 호환) |
| searchDate 필드 | 인덱싱/쿼리 최적화를 위해 YYYY-MM-DD 문자열로 별도 저장/응답 |
| 목표 분석 | create 시 settings 로드 → goal_analysis 포함 (meal/activity/weight) |
| 달성 알림 | 최초 100% 달성 순간에만 `PET_CARE_GOAL_REACHED` 발송 (meal/activity/weight) |
| 캐시 무효화 | 기록 생성 시 해당 날짜 캐시 키 무효화 (daily/range) |

## 엔드포인트 요약
| Method | Path | Auth | 설명 | 성공 | 주요 오류 코드 |
|---|---|---|---|---|---|
| POST | /api/pet-care/{pet_id}/records | jwt_required | 단일 기록 생성 + goal_analysis | 201 | VALIDATION_ERROR, RECORD_CREATION_FAILED |
| GET | /api/pet-care/{pet_id}/records/daily?date=YYYY-MM-DD | jwt_required | 특정 날짜 기록 + summary | 200 | VALIDATION_ERROR, FETCH_FAILED, NOT_FOUND |
| GET | /api/pet-care/{pet_id}/records/range?start_date&end_date | jwt_required | 기간별 기록 그룹 + trends + goal_tracking | 200 | VALIDATION_ERROR, FETCH_FAILED |
| PATCH | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | data/memo 부분 수정 | 200 | VALIDATION_ERROR, NOT_FOUND, FORBIDDEN, UPDATE_FAILED |
| DELETE | /api/pet-care/{pet_id}/records/{log_id} | jwt_required | 기록 삭제 | 204 | NOT_FOUND, FORBIDDEN, DELETE_FAILED |

이전 문서의 범용 listing(by type, generic query) 엔드포인트는 현재 구현 코드 기준 비활성/미구현 상태이므로 명세에서 제외.

## record_type & data 구조
| record_type | data 예시 구조 | 제약 |
|---|---|---|
| meal | 단순 정수 카운트 또는 `{}` (구현단에서는 meal_count 레거시 반영 시 길이==1 누적) | 1회 추가당 +1, 음수 불가 |
| activity | `{ "duration": <int 분> }` 또는 정수(구버전) | 0..1440 범위, create 시 누적 진행률 계산 |
| weight | `{ "weight": <float kg> }` 또는 float(구버전) | 0.1..200.0 |
| bcs | `{ "score": <1~9> }` 또는 int | 1..9 |
| stool | `{ "consistency": "firm|soft|loose", "color": "...", ... }` | 자유 확장 객체, 주요 키 consistency |
| vomit | `{ "count": <int>, "color": "..." }` | count ≥0 |

내부 서비스는 다양한 레거시 형태(number vs object)를 수용해 Firestore에 그대로 저장 후 응답 시 동일 구조 반환. 새 클라이언트는 객체 형태 사용 권장.

## 생성 (POST) 요청 스키마
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| record_type | string(enum: meal, activity, weight, bcs, stool, vomit) | ✔ | 기록 타입 |
| timestamp | int(ms epoch) | ✔ | 클라이언트 UTC 기준 ms. 서버에서 Date 변환 후 searchDate 생성 |
| data | number or object | ✔ | 위 타입별 규칙 참조 |
| memo | string |  | 선택, 500자 내 권장 |
| user_id | string |  | 내부 추적(서버가 주입 가능) |

응답 필드 (생성)
| 필드 | 설명 |
|---|---|
| log_id | 기록 고유 ID (UUID4) |
| pet_id | 펫 ID |
| record_type | 동일 입력값 |
| timestamp, timestamp_ms | ms 정수 (동일 값) |
| searchDate | YYYY-MM-DD (쿼리 인덱스 키) |
| data, memo | 원본/수정 데이터 |
| user_id | 작성자 추적용 |
| goal_analysis | (옵션) settings 존재 시 { date, goals{}, achievements{}, recommendations[] } |

goal_analysis.achievements 예시
```json
{
	"meal_count": { "actual": 2, "goal": 3, "percentage": 66.7, "achieved": false },
	"activity_duration": { "actual": 40, "goal": 60, "percentage": 66.7, "achieved": false, "unit": "minutes" },
	"current_weight": { "actual": 6.3, "goal": 6.2, "difference": 0.1, "at_goal": false, "unit": "kg" }
}
```

## 일별 조회 (GET /daily)
쿼리 파라미터: `date` (YYYY-MM-DD) 필수.

응답
| 필드 | 설명 |
|---|---|
| date | 조회 날짜 |
| records[] | 원시 기록 배열 (create 응답 구조와 유사) |
| summary | { meal_count, activity_minutes, weight, bcs, stool, vomit } (미존재 항목 null) |
| record_counts (goal 확장 경로) | 타입별 개수 (integration 사용 시) |
| goal_progress (goal 확장 경로) | `_analyze_daily_goals` 결과 |
| meta | (확장 예정) |

## 기간 조회 (GET /range)
쿼리 파라미터: `start_date`, `end_date` (YYYY-MM-DD). 최대 기간 제한은 서버 내부 정책(문서화 보류).

응답
| 필드 | 설명 |
|---|---|
| start_date/end_date | 요청 범위 |
| records_by_date.{date}[] | 해당 날짜 기록 배열 |
| trends | { weight_trend[], meal_frequency_trend[], activity_trend[] } |
| goal_tracking | { period{}, daily_achievements{}, overall_stats{} } |
| meta | 페이징/추가 정보 (구현 확장 시) |

### trends.* 예시
| 배열 | 원소 구조 |
|---|---|
| weight_trend | { date, weight } |
| meal_frequency_trend | { date, meal_count } |
| activity_trend | { date, activity_duration } |

### goal_tracking.overall_stats 예시
```json
{
	"total_days": 7,
	"goal_achievement_rates": {
		"meal": 71.4,
		"activity": 57.1,
		"weight": 28.6
	}
}
```

## 수정 (PATCH)
요청 바디: `{ "data": <타입별 구조>, "memo": "문자열" }` (둘 중 하나 이상). 부분 업데이트, timestamp/searchDate 불가.
응답: 갱신된 기록 (create 구조 + updated_at? Firestore timestamp 직렬화 시 내부 변환; 별도 필드 스펙 없음).

## 삭제 (DELETE)
성공 시 204 No Content (기존 문서 200 → 실제 구현 204 로 일치).

## 에러 코드
| 상황 | error_code | 비고 |
|---|---|---|
| 인증 없음/무효 | MISSING_JWT / INVALID_JWT | 공통 |
| 유효성 실패 | VALIDATION_ERROR | 스키마/필드 범위 위반 |
| 찾을 수 없음 | NOT_FOUND | log_id 또는 pet_id 불일치 |
| 권한 없음 | FORBIDDEN | 펫 소유자 아님 |
| 생성 실패 | RECORD_CREATION_FAILED | 내부 예외 래핑 |
| 수정 실패 | UPDATE_FAILED | 내부 예외 래핑 |
| 삭제 실패 | DELETE_FAILED | 내부 예외 래핑 |
| 조회 실패 | FETCH_FAILED | 일/범위 조회 예외 |

응답 에러 포맷: `{ "code": "<error_code>", "message": "..." }` (전역 catalog 적용 영역 확장 중).

## 저장 구조 & 인덱스
| 항목 | 내용 |
|---|---|
| 컬렉션 | `pet_care_logs` |
| 문서 키 | `log_id` (UUID4) |
| 필드 | log_id, pet_id, record_type, timestamp(Firestore datetime), searchDate, data, memo, user_id |
| 인덱싱 | (pet_id, searchDate, timestamp) 복합 색인 권장 (일/기간 정렬) |
| searchDate 생성 | `DateTimeUtils.from_timestamp_ms` → `to_date_str` |

## 목표 달성 알림 로직 (Achievement Notifications)
| 항목 | 내용 |
|---|---|
| 적용 대상 | meal_count(식사), activity_duration(활동), weight(체중) |
| 트리거 시점 | create 후 goal_analysis 계산 직후 |
| 조건 | 해당 목표 100% 이상 도달 & 직전 상태 < 100% (weight는 허용 오차 ±0.1kg 내) |
| 알림 타입 | `PET_CARE_GOAL_REACHED` (NotificationType) |
| 메시지 예 | 식사: 🎉 ... 식사 목표 달성, 활동: 🏃 ... 활동 목표 달성, 체중: ⚖️ ... 목표 체중 달성 |
| metrics | `pet_care_achievement_notifications_sent` (notification_types=comma list) |
| 중복 방지 | 이전 actual < goal / at_goal false 조건 기반 (별도 상태 문서 없이 현재 분석 결과로 판정) |

주의: UPDATE/DELETE 는 목표 달성 롤백 처리하지 않음 (1회성 축하 정책).

## 베스트 프랙티스
1. weight/activity/meal 은 객체 형태 사용 (미래 확장: 단위, 메타데이터 추가)  
2. 클라이언트는 timezone 을 UTC 로 변환 후 ms epoch 제공  
3. 빈/중복 create 방지: 클라이언트 자체 디바운싱 (서버 멱등키 현재 미구현)  
4. range 조회는 필요한 최소 기간만 요청 (trends 계산 비용 감소)  
5. goal_analysis 필요 없으면 settings 미요청 캐시 전략(추후) 고려

## 향후 개선 예정 (문서화)
| 항목 | 설명 |
|---|---|
| 멱등키 지원 | request_id 기반 중복 기록 방지 |
| Daily Summary Notification | PET_CARE_DAILY_SUMMARY 자동 생성 (Enum 준비됨) |
| 부분 집계 캐시 | 일별 합/횟수 캐싱으로 range 성능 향상 |
| 데이터 정규화 | number vs object 혼합 구조 통일 |
