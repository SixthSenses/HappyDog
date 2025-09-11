# cartoon_jobs API

그림체 변환 작업(cartoon_jobs) 도메인 API 요약입니다.

## 엔드포인트 요약

| Method | Path | Auth | 역할/설명 | Status |
|---|---|---|---|---|
| POST | /api/cartoon-jobs/ | jwt_required | 그림체 변환 작업 생성(비동기) | 202, 400, 401, 500 |
| GET | /api/cartoon-jobs/{job_id} | jwt_required | 내 작업 상태/결과 조회 | 200, 401, 404, 500 |
| DELETE | /api/cartoon-jobs/{job_id} | jwt_required | 진행 중 작업 취소(cancelling 전이) | 200, 401, 403, 404, 409, 500 |

## 요청/응답 스키마

| 스키마 | 필드 | 타입 | 필수 | 비고 |
|---|---|---|---|---|
| CartoonJobCreateSchema | file_paths | array<URL>[min 1] | ✔ |  |
|  | user_text | string(≤500) |  | optional |
| CartoonJobResponseSchema | job_id | UUID | ✔ |  |
|  | user_id | UUID | ✔ |  |
|  | status | string(enum) | ✔ |  |
|  | original_image_url | URL | ✔ |  |
|  | user_text | string |  | optional |
|  | result_image_url | URL |  | optional |
|  | error_message | string |  | optional |
|  | created_at/updated_at | ISO8601 | ✔ |  |

## 오류/예외

| 엔드포인트 | 4xx/5xx | 조건 |
|---|---|---|
| POST / | 400 VALIDATION_ERROR | 스키마 검증 실패 |
|  | 500 JOB_CREATION_FAILED | 서버 오류 |
| GET /{id} | 404 JOB_NOT_FOUND_OR_FORBIDDEN | 미존재/권한 없음 |
|  | 500 INTERNAL_SERVER_ERROR | 서버 오류 |
| DELETE /{id} | 403 FORBIDDEN | 권한 없음 |
|  | 409 INVALID_STATE_FOR_CANCEL | 상태 부적합 |
|  | 404 JOB_NOT_FOUND | 미존재 |
|  | 500 JOB_CANCEL_FAILED | 서버 오류 |

### 오류 메시지 예시

| Status | error_code | 예시 message |
|---|---|---|
| 401 | UNAUTHORIZED | 인증이 필요합니다. 액세스 토큰이 없거나 만료되었습니다. |
| 403 | FORBIDDEN | 이 작업을 수행할 권한이 없습니다. |
| 404 | JOB_NOT_FOUND/JOB_NOT_FOUND_OR_FORBIDDEN | 작업을 찾을 수 없거나 권한이 없습니다. |
| 409 | INVALID_STATE_FOR_CANCEL | 현재 상태에서는 취소할 수 없습니다. |
| 500 | INTERNAL_SERVER_ERROR/JOB_CREATION_FAILED/JOB_CANCEL_FAILED | 서버 내부 오류가 발생했습니다. |

## 저장/비즈니스 로직

| 단계 | 내용 |
|---|---|
| 1 | cartoon_jobs에 job 생성(status=processing) |
| 2 | 백그라운드에서 OpenAIService.generate_cartoon 실행 |
| 3 | 성공 시 result_image_url 저장 + PostService.create_post + CARTOON_SUCCESS 알림 |
| 4 | 실패 시 status=failed, error_message 저장 + CARTOON_FAILED 알림 |
| 5 | 취소 요청은 status=canceling 전이(Cloud Function 처리) |

### 멱등성/202/취소 흐름
- 멱등성: POST /api/cartoon-jobs/ 호출 시 X-Idempotency-Key 헤더를 제공하면 동일 요청 재시도에도 같은 202 응답이 재사용됩니다. 응답 헤더에 `Idempotent-Replay: true` 가 포함될 수 있습니다.
- 응답 패턴: 생성 시 즉시 202와 함께 processing 상태의 작업 정보가 반환되며, 실제 만화 생성은 백그라운드에서 진행됩니다.
- 취소 흐름: DELETE 호출 시 상태가 processing이면 canceling으로 전환됩니다. 백그라운드 작업이 이를 감지하면 실패 처리로 종료되어 중복 완료를 방지합니다.
