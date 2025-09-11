# cartoon_jobs API (코드 기준 최신 스펙)

만화(그림체) 변환 비동기 작업 도메인. Swagger 문서는 부분적으로 구버전이므로 아래 표가 단일 진실 원천(source of truth)입니다.

## 1. 엔드포인트

| Method | Path | Auth | 설명 | 정상 Status | 비고 |
|---|---|---|---|---|---|
| POST | /api/cartoon-jobs/ | 필수 | 만화 변환 작업 생성 (비동기) | 202 | 즉시 PENDING 반환, 백그라운드 전환 |
| GET | /api/cartoon-jobs/{job_id} | 필수 | 내 작업 상태/결과 조회 | 200 | 권한: 소유자만 |
| DELETE | /api/cartoon-jobs/{job_id} | 필수 | 작업 취소 요청 | 200 | 상태별 분기 (즉시/전이) |
| GET | /api/cartoon-jobs/health | 공개 | 작업 프로세서 헬스 체크 | 200 | 운영 관찰용 |

## 2. 상태 모델 (Enum)

| 상태 | 의미 | 전이 트리거 |
|---|---|---|
| pending | 생성 직후 (워커 투입 전) | create_job |
| processing | 워커에서 실제 변환 수행 중 | job_events.handle_job_created → 워커 픽업 |
| completed | 성공 완료 (result_image_url 세팅) | 워커 처리 성공 |
| failed | 실패 종료 (error_message 세팅) | 워커 예외 / 통합 실패 |
| canceling | 사용자가 취소 요청, 워커가 중간/대기 상태 | DELETE (processing 상태) |
| cancelled | 최종 취소 완료 | (a) pending 즉시 취소, (b) canceling → 워커 확인 |

## 3. 요청/응답 스키마

### 3.1 생성 요청 (CartoonJobCreateSchema)
| 필드 | 타입 | 제약 | 비고 |
|---|---|---|---|
| file_paths | list<URL> | 길이=1 (min=1,max=1) | 단일 이미지만 지원 |
| user_text | string | ≤500자, optional | 프롬프트/주석 용도 |

### 3.2 공용 응답 (CartoonJobResponseSchema)
모든 생성/조회/취소 응답 공통.

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| job_id | string(UUID 형식) | ✔ | 작업 식별자 |
| user_id | string | ✔ | 소유 사용자 |
| status | string(enum) | ✔ | 위 상태 모델 |
| original_image_url | URL | ✔ | 업로드된 원본 이미지 |
| user_text | string|null |  | 입력 텍스트 |
| result_image_url | URL|null |  | completed 에서 세팅 |
| error_message | string|null |  | 실패/취소 사유(취소 시 '사용자가 작업을 취소했습니다') |
| created_at | ISO8601 | ✔ | 생성 시각 (UTC) |
| updated_at | ISO8601 | ✔ | 최신 변경 시각 |

### 3.3 예시
생성 (202):
```
{
	"job_id": "6f0e9c2a-...",
	"user_id": "user_123",
	"status": "pending",
	"original_image_url": "https://storage.googleapis.com/.../orig.jpg",
	"user_text": "귀엽게 변환",
	"result_image_url": null,
	"error_message": null,
	"created_at": "2025-01-10T12:00:00Z",
	"updated_at": "2025-01-10T12:00:00Z"
}
```

완료 (200):
```
{
	"job_id": "6f0e9c2a-...",
	"user_id": "user_123",
	"status": "completed",
	"original_image_url": "https://.../orig.jpg",
	"result_image_url": "https://.../result.jpg",
	"user_text": "귀엽게 변환",
	"error_message": null,
	"created_at": "2025-01-10T12:00:00Z",
	"updated_at": "2025-01-10T12:02:31Z"
}
```

취소 (pending 즉시 / 200):
```
{
	"job_id": "6f0e9c2a-...",
	"user_id": "user_123",
	"status": "cancelled",
	"original_image_url": "https://.../orig.jpg",
	"result_image_url": null,
	"error_message": "사용자가 작업을 취소했습니다",
	"user_text": "귀엽게 변환",
	"created_at": "2025-01-10T12:00:00Z",
	"updated_at": "2025-01-10T12:00:05Z"
}
```

취소 요청 (processing → canceling, 아직 최종 아님 / 200):
```
{
	"job_id": "6f0e9c2a-...",
	"status": "canceling",
	...
}
```

헬스 (200):
```
{
	"active_jobs": 3,
	"queue_size": 5,
	"max_workers": 4,
	"integration_health": {"status": "healthy", "last_check": "2025-01-10T12:00:00Z"}
}
```

## 4. 오류 코드 (실제 routes.py build_error 사용 기준)

| 엔드포인트 | 코드 | Http | 조건/설명 |
|---|---|---|---|
| POST / | VALIDATION_ERROR | 400 | 스키마 검증 실패 (Marshmallow) |
|  | RECORD_CREATION_FAILED | 500 | Firestore 저장/내부 예외 |
| GET /{id} | NOT_FOUND | 404 | 존재하지 않거나 소유자 불일치 |
|  | FETCH_FAILED | 500 | 조회 중 내부 오류 |
| DELETE /{id} | FORBIDDEN | 403 | 소유자 아님(PermissionError) |
|  | OUT_OF_RANGE | 400 | (1) 존재하지 않음 (취소 시점 ValueError) 또는 (2) 취소 불가 상태 ValueError 메시지 |
|  | UPDATE_FAILED | 500 | 취소 처리 중 일반 예외 |
| GET /health | SERVICE_UNAVAILABLE | 503 | 헬스 정보 수집 실패 |

주의: Swagger에 표기된 INVALID_STATE_FOR_CANCEL / JOB_CANCEL_FAILED 등은 구버전 용어. 현재 코드에서는 OUT_OF_RANGE / UPDATE_FAILED 로 매핑되어 있으므로 문서도 실제 코드에 맞춤.

## 5. 비즈니스 플로우

1. create_job → 상태 pending 저장
2. job_events.handle_job_created: 워커 큐 투입 → processing 전환
3. 워커 처리 성공 → status=completed, result_image_url 세팅, PostService.create_post & CARTOON_SUCCESS 알림
4. 워커 실패 → status=failed, error_message 세팅, CARTOON_FAILED 알림
5. 사용자 취소:
	 - pending: 즉시 cancelled + error_message="사용자가 작업을 취소했습니다"
	 - processing: canceling 전이 → 워커 확인 후 cancelled 최종 확정

## 6. 멱등성 (Idempotency)
| 항목 | 내용 |
|---|---|
| 헤더 | X-Idempotency-Key (클라이언트가 생성한 고유 문자열) |
| 재시도 | 동일 키 + 동일 Body ⇒ 최초 생성된 job의 202 응답 재사용 |
| 재생 표시 | 응답 헤더에 Idempotent-Replay: true (재생 시) |
| 실패 시 | 키-응답 매핑 저장 전 에러 발생하면 신규 시도 가능 |

## 7. 설계 주석 & 향후 개선
| 이슈 | 현상 | 개선 아이디어 |
|---|---|---|
| OUT_OF_RANGE 오용 | 취소 불가와 존재하지 않음 혼재 | 에러 카탈로그 통일(PR4)시 INVALID_STATE / NOT_FOUND 분리 |
| 상태 중복 전이 | canceling→cancelled polling 지연 | 워커 즉시 확인 최적화 또는 pub/sub 이벤트화 |
| 단일 이미지 제한 | file_paths 길이=1 | 멀티 이미지 batch 변환 요구 검토 |
| Post 생성 타이밍 | 완료 즉시 게시 | 사용자가 게시 승인 단계를 원할 수 있음 (draft) |

---
문서 버전: 2025-09 코드 스냅샷 기준 (routes.py, job_service.py, models/cartoon_job.py)
