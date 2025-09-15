# pet_care/settings API (Code-first)

펫 케어 목표/기준값 관리. 기록(create) 시 goal_analysis 계산 및 달성 알림(`PET_CARE_GOAL_REACHED`) 판단의 근거..

## 최근 변경 사항
| 변경 | 내용 |
|---|---|
| 필드 명세 통일 | daily_meal_count / target_daily_meal_count / target_daily_activity_minutes / daily_activity_increment / target_weight |
| 부분 업데이트 | PUT 시 전달 필드만 수정(partial=True) |
| 오류 코드 정규화 | NOT_FOUND, VALIDATION_ERROR, UPDATE_FAILED, FETCH_FAILED 사용 |
| daily_activity_increment | 활동 권장 증분(min) separate 필드 (레코드 추천/미래 확장) |

## 엔드포인트
| Method | Path | Auth | 설명 | 성공 | 주요 오류 |
|---|---|---|---|---|---|
| GET | /api/pet-care/{pet_id}/settings | jwt_required | 설정 조회 | 200 | NOT_FOUND, FETCH_FAILED |
| PUT | /api/pet-care/{pet_id}/settings | jwt_required | 설정 부분 수정 | 200 | VALIDATION_ERROR, NOT_FOUND, UPDATE_FAILED |

## 스키마 (PetCareSettingsSchema)
| 필드 | 타입 | 요구/범위 | 비고 |
|---|---|---|---|
| daily_meal_count | int | 1..10 (required) | 기본 하루 식사 횟수(현재 소비용) |
| target_daily_meal_count | int | 1..10 (required) | 목표 식사 횟수(달성 판단) |
| target_daily_activity_minutes | int | 0..1440 (required) | 목표 활동 시간(분) |
| daily_activity_increment | int | 1..180 (required) | 활동 추가 단위(분) UI 가이드 |
| target_weight | float | 0.1..200.0 (required) | 목표 체중(kg) |
| pet_id | string | dump_only | 문서 ID (=pet_id) |
| updated_at | ISO8601 | dump_only | Firestore timestamp 직렬화 |

응답 예
```json
{
	"pet_id": "pet_123",
	"daily_meal_count": 2,
	"target_daily_meal_count": 3,
	"target_daily_activity_minutes": 120,
	"daily_activity_increment": 15,
	"target_weight": 26.5,
	"updated_at": "2024-01-01T12:00:00Z"
}
```

### PUT 부분 업데이트
전달된 필드만 반영. 빈 객체 또는 null → VALIDATION_ERROR("수정할 데이터가 없습니다.").

## 오류 코드
| 상황 | error_code | 비고 |
|---|---|---|
| 인증 없음/무효 | MISSING_JWT / INVALID_JWT | 공통 미들웨어 |
| 설정 없음 | NOT_FOUND | FileNotFoundError 매핑 |
| 유효성 실패 | VALIDATION_ERROR | Marshmallow ValidationError |
| 수정 실패 | UPDATE_FAILED | 내부 예외 |
| 조회 실패 | FETCH_FAILED | 기타 예외 |

에러 응답 포맷: `{ "code": "<error_code>", "message": "..." }`.

## 저장 구조
| 항목 | 내용 |
|---|---|
| 컬렉션 | `pet_settings` |
| 문서 키 | pet_id (pets 1:1) |
| 필드 | daily_meal_count, target_daily_meal_count, target_daily_activity_minutes, daily_activity_increment, target_weight, updated_at |
| 최초 생성 | 트랜잭션 util (품종/성별 기반 기본값 산출 – 상세 로직 별도 문서화 예정) |
| 업데이트 | partial merge, updated_at 갱신 |

## Goal Analysis 와의 관계
| 영역 | 사용 필드 | 용도 |
|---|---|---|
| meal 목표 | target_daily_meal_count | 목표 달성율 계산 & 100% 달성 알림 |
| activity 목표 | target_daily_activity_minutes | duration 합계 비교 |
| weight 목표 | target_weight | ±0.1kg 오차 내 달성 판단 |
| 추천(향후) | daily_activity_increment | 다음 활동 권장 증분 계산 베이스 |

## 베스트 프랙티스
1. target vs daily 구분: target_* 필드는 “목표” 판단, daily_meal_count 는 기본/평균 레퍼런스.  
2. weight 조정은 소수 첫째자리 유지(측정 입력은 원본 저장).  
3. 활동 목표 0 설정 시 활동 목표 관련 알림/분석 비활성.  
4. 클라이언트는 필요 없는 필드 제외하고 PUT (불필요 충돌 감소).  
5. 설정 갱신 후 직후 기록 생성하면 새 목표 기준으로 달성 판단.

## 향후 개선 예정
| 항목 | 설명 |
|---|---|
| Daily Summary Notification | PET_CARE_DAILY_SUMMARY 생성 로직 연계 |
| 증분 추천 알고리즘 | daily_activity_increment 기반 동적 제안 |
| 사용자 커스터마이징 | 목표 별 알림 on/off 플래그 추가 |
| Weight trend adaptive goal | 체중 안정 시 목표 자동 재설정 옵션 |
