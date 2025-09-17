# 딥링크 & 멱등성 가이드

본 문서는 프론트엔드와 앱 클라이언트가 실제 연동할 때 필요한 딥링크 처리 원칙과, 쓰기 요청의 멱등성 보장을 위한 규칙/헤더/응답 규약을 정리합니다.

---

## 딥링크(Deep Link)

현재 백엔드 레포에는 전용 딥링크 라우트는 존재하지 않습니다(서버가 링크를 해석해 다른 스킴으로 리다이렉트하는 엔드포인트 없음). 대신 다음 두 가지 상황을 고려해 클라이언트가 동작하면 됩니다.

- 인증 흐름(구글 OAuth)
  - 시작: `GET /api/auth/google/authorize`
    - `?redirect=1`이면 구글 동의 화면으로 302 리다이렉트합니다.
    - 아니면 JSON으로 `authorization_url`, `redirect_uri`, `state`를 반환합니다.
  - 콜백: `GET /api/auth/social?code=...`
    - 구글이 인증 후 브라우저를 이 엔드포인트로 리다이렉트합니다.
  - 토큰 교환(프론트 전용): `POST /api/auth/social` body에 `auth_code`를 포함합니다.
- 앱 내 딥링크 처리
  - 모바일/웹 앱은 자체 스킴(예: `happydog://...`) 또는 웹 라우팅으로 화면 이동을 수행합니다.
  - 서버는 현재 앱 스킴으로 리다이렉트하는 별도의 엔드포인트를 제공하지 않습니다. 필요 시 `/docs`에 별도 표기 후 경로를 추가할 수 있습니다.

권장 사항
- 앱이 웹 링크를 받을 때, 로그인 상태/권한에 따라 내부 라우팅으로 적절한 화면을 열어 주세요.
- OAuth 콜백은 서버가 처리하므로 앱 전용 콜백 스킴은 사용하지 않습니다(현 구조 기준).

---

## 멱등성(Idempotency)

쓰기(POST/PUT/PATCH) 요청에서 중복 전송이나 재시도에도 안전하게 처리되도록 멱등성을 제공합니다. 핵심은 `X-Idempotency-Key` 헤더입니다.

### 적용 방식
- 미들웨어: `app.middleware.idempotency_middleware.idempotent_endpoint`
- 서비스: `app.services.idempotency_service.IdempotencyService`
- 저장소: Firestore 컬렉션 `idempotency_keys`

### 요청 규약
- 헤더: `X-Idempotency-Key: <클라이언트가 생성한 유니크 키>`
  - 키는 UUIDv4 권장. 동일한 키는 동일한 요청 본문과 함께 사용해야 합니다.
- 메서드: 기본 적용 범위는 `POST|PUT|PATCH`이며, 아래 명시된 특정 엔드포인트에서는 `DELETE`에도 적용됩니다.
- 본문: JSON 본문은 canonical hash로 비교합니다. 동일 키 + 다른 본문이면 409 충돌을 반환합니다.

### 응답 규약
- 상태코드/본문은 최초 성공 응답을 기준으로 재사용됩니다.
- 재사용 여부는 헤더로 표기됩니다:
  - `Idempotent-Replay: true` (신규 표준)
  - `Idempotency-Replay: true` (과도기 호환; 점차 폐기 예정)
- 항상 `Idempotency-Key` 헤더를 응답에 되돌려줍니다.

### 에러 케이스
- 키 재사용 + 본문 다름: `409 Conflict` + `error_code=IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY`
- 내부 오류: `500`대 오류 + `error_code=FETCH_FAILED` (향후 세분화 가능)

### 적용 엔드포인트
아래 엔드포인트에는 멱등성 데코레이터가 적용되어 있으며, 재시도/중복 전송 시 동일 키를 사용하면 최초 성공 응답이 재사용됩니다.

- `POST /api/auth/social` — 소셜 로그인 코드 교환
- `POST /api/posts` — 게시글 생성
- `POST /api/comments/posts/{post_id}/comments` — 댓글 생성
- `POST /api/pet-care/{pet_id}/records` — 케어 기록 생성
- `POST /api/pets` — 반려견 등록
- `POST /api/pets/{pet_id}/nose-print` — 비문 등록
- `POST /api/pets/{pet_id}/eye-analysis` — 안구 분석 요청
- `POST /api/notifications/{notification_id}/ack` — 알림 확인
- `POST /api/cartoon-jobs` — 카툰 작업 생성
- `DELETE /api/cartoon-jobs/{job_id}` — 카툰 작업 취소 (DELETE에도 멱등 적용)

참고: 기타 엔드포인트는 현재 멱등성 데코레이터가 적용되어 있지 않습니다. 높은 중복/재시도 가능성이 있는 쓰기 요청에 우선 적용했습니다.

### 샘플
- 요청
```
POST /api/posts HTTP/1.1
Content-Type: application/json
X-Idempotency-Key: 0d3de5a8-6a9c-4c6b-9b8e-9c5d1c5fb0a7

{"title":"안녕","content":"첫 글"}
```
- 최초 응답(예)
```
HTTP/1.1 201 Created
Idempotency-Key: 0d3de5a8-6a9c-4c6b-9b8e-9c5d1c5fb0a7

{"postId":"...","title":"안녕","content":"첫 글"}
```
- 동일 키 재전송 응답(예)
```
HTTP/1.1 201 Created
Idempotency-Key: 0d3de5a8-6a9c-4c6b-9b8e-9c5d1c5fb0a7
Idempotent-Replay: true

{"postId":"...","title":"안녕","content":"첫 글"}
```
- 본문이 달라진 경우
```
HTTP/1.1 409 Conflict
Content-Type: application/json

{"error_code":"IDEMPOTENCY_KEY_REUSED_DIFFERENT_BODY","category":"CONFLICT","retriable":false}
```

#### DELETE 예시 (카툰 작업 취소)
```
DELETE /api/cartoon-jobs/abc123 HTTP/1.1
X-Idempotency-Key: 6b6af4ca-f8b3-4f5c-9e20-3d0f2e8c9a11
```
응답(최초 또는 재사용)
```
HTTP/1.1 200 OK
Idempotency-Key: 6b6af4ca-f8b3-4f5c-9e20-3d0f2e8c9a11
Idempotent-Replay: true

{"jobId":"abc123","status":"CANCELLED"}
```

---

## 프런트 권장 구현
- 키 생성: 각 쓰기 액션마다 UUID 생성 후 요청 헤더에 첨부. 백오프 재시도 시 동일 키 유지.
- 캐싱: 409가 발생하면 키/본문 매칭을 재검토하고, 동일 본문으로만 재요청.
- UI: 재전송으로 인한 중복 생성이 눈에 띄지 않도록, 재사용 응답(`Idempotent-Replay`)이면 성공 토스트만 보여주고 중복 알림은 생략.

---

## FAQ
- Q. GET에도 키를 붙이면 멱등 처리되나요?
  - A. 기본 구현은 쓰기 메서드(POST/PUT/PATCH)에만 적용합니다. GET은 무시됩니다.
- Q. 키는 언제 만료되나요?
  - A. 현재 만료 정책은 서버에서 별도 삭제 배치 없이 영구 보관을 가정합니다(변경 예정 시 공지). 프런트는 동일 키를 재사용하지 않는 것이 원칙입니다.
- Q. 본문이 큰 경우에도 저장되나요?
  - A. 최초 응답 본문은 Firestore에 저장됩니다. 너무 큰 페이로드는 피하고, 필요 시 서버가 축약된 응답을 저장하도록 변경할 수 있습니다.
