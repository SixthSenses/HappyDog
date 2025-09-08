## 공통 규약

- 시간/타임존: UTC 고정. Firestore Timestamp는 DateTimeUtils.for_firestore를 통해 저장.
- 에러 포맷: { error_code, message?, details? } (전역 ValidationError 핸들러 존재).
- 인증: flask_jwt_extended 기반, 일부 엔드포인트에 @jwt_required 적용.

### 자료형 표기 규칙
- string: 문자열 (UUID/URL/ISO8601는 별도 표기)
- int/float: 숫자형
- boolean: 불리언
- ISO8601: UTC 기반 날짜/시간 문자열("YYYY-MM-DD" 또는 "YYYY-MM-DDTHH:mm:ssZ")
- timestamp(ms): Unix epoch milliseconds (int)
- UUID: 문자열 UUID
- URL: 문자열 URL
- object: JSON 오브젝트, array<T>: 제네릭 배열

## 1) auth

### 엔드포인트

- POST /api/auth/social — 소셜 로그인/회원가입 처리 (Google 코드 교환 → 토큰 발급)
- POST /api/auth/token/refresh — Refresh 토큰으로 Access 토큰 재발급
- POST /api/auth/logout — 전달된 access/refresh JWT 블랙리스트 처리(서버 로그아웃)

### 요청 스키마/입력

- SocialLoginSchema: { provider: string, auth_code: string }
- LogoutRequestSchema: { access_token: string(JWT), refresh_token: string(JWT) }

### 응답/출력

- /social: 200 { access_token, refresh_token, user_id, is_new_user, user_info{ user_id,email,nickname,profile_image_url } } | 401 INVALID_AUTH_CODE | 500 INTERNAL_SERVER_ERROR
- /token/refresh: 200 { access_token } (헤더의 refresh JWT 검증은 데코레이터 처리)
- /logout: 200 { message } | 400 VALIDATION_ERROR | 422 INVALID_TOKEN | 500 LOGOUT_FAILED

### 데이터 타입 요약
- /social Response: { access_token: string, refresh_token: string, user_id: UUID, is_new_user: boolean, user_info: { user_id: UUID, email: string, nickname: string, profile_image_url: URL|null } }
- /token/refresh Response: { access_token: string }
- /logout Response: { message: string }

### 데이터 저장/검증 로직

1. GoogleAuthService.exchange_code_for_user_info로 userinfo 조회 → AuthService.get_or_create_user_by_google로 users 컬렉션 upsert.
2. 신규: user_id(UUID), google_id(sub), email, nickname(name), join_date(UTC) 등 저장.
3. 로그아웃: access/refresh JWT를 서명검증 없이 디코드(verify_exp=False) → jti/exp 추출 → revoked_tokens 컬렉션에 {revoked_at, expires_at} 저장.

기타: AuthService.delete_user_account는 Firebase Auth에서 사용자 삭제(확장으로 데이터 정리).

## 2) breeds

### 엔드포인트

- GET /api/breeds/ — 품종 목록/요약 목록 조회 (limit/offset/summary)
- GET /api/breeds/{breed_name} — 특정 품종 단건 조회
- GET /api/breeds/search?q=...&limit&offset — 부분 문자열 검색(클라 필터)
- GET /api/breeds/exists/{breed_name} — 해당 품종 존재 여부 확인
- GET /api/breeds/statistics — 품종 통계 조회(합/평균/최소/최대)

### 스키마/데이터 형식
- 데이터 타입 요약
    - Breed.height_cm, weight_kg: object { male: float, female: float }
    - life_expectancy: float(0~30)
    - created_at/updated_at: ISO8601

- BreedSchema: { breed_name, life_expectancy(float 0-30), height_cm{male,female}, weight_kg{male,female}, created_at?, updated_at? }
- BreedListSchema: { breeds: Breed[], total_count:int } / SummaryList는 { breed_name, life_expectancy }만.

### 응답/오류 케이스

- 공통 400 VALIDATION_ERROR(마시멜로 핸들러).
- GET /: 200 BreedList|SummaryList | 400 INVALID_PARAMETER | 500 BREED_FETCH_FAILED
- GET /{name}: 200 Breed | 404 BREED_NOT_FOUND | 500 BREED_FETCH_FAILED
- GET /search: 200 BreedList | 400 MISSING_PARAMETER/INVALID_PARAMETER | 500 BREED_SEARCH_FAILED
- GET /exists/{name}: 200 {breed_name, exists} | 500 BREED_CHECK_FAILED
- GET /statistics: 200 stats | 500 STATS_FETCH_FAILED

### 저장/조회 로직

1. 컬렉션: breeds (doc ID=breed_name). get_all_breeds는 order_by('breed_name') 기반, offset은 start_after로 구현.
2. search는 전체 로드 후 파이썬에서 부분 문자열 필터(대소문자 무시) → offset/limit 슬라이싱.
3. get_statistics는 life_expectancy 집계로 평균/최소/최대 계산.

## 3) cartoon_jobs

### 엔드포인트

- POST /api/cartoon-jobs/ — 그림체 변환 작업 생성(비동기, 202)
- GET /api/cartoon-jobs/{job_id} — 내 작업 상태/결과 조회
- DELETE /api/cartoon-jobs/{job_id} — 진행 중 작업 취소(cancelling 전이)

### 입력/스키마

- CartoonJobCreateSchema: { file_paths: array<URL>[min 1], user_text?: string(≤500) }

### 출력

- CartoonJobResponseSchema: { job_id,user_id,status,original_image_url,user_text?,result_image_url?,error_message?,created_at,updated_at }

### 오류 케이스

- POST /: 400 VALIDATION_ERROR | 500 JOB_CREATION_FAILED
- GET /{id}: 404 JOB_NOT_FOUND_OR_FORBIDDEN | 500 INTERNAL_SERVER_ERROR
- DELETE /{id}: 403 FORBIDDEN | 409 INVALID_STATE_FOR_CANCEL | 404 JOB_NOT_FOUND | 500 JOB_CANCEL_FAILED

### 저장/비즈니스 로직
### 데이터 타입 요약
- CartoonJobResponseSchema: { job_id: UUID, user_id: UUID, status: string(enum), original_image_url: URL, user_text?: string, result_image_url?: URL, error_message?: string, created_at: ISO8601, updated_at: ISO8601 }

1. Firestore cartoon_jobs 컬렉션에 job_id(UUID)로 문서 생성, status=processing.
2. 백그라운드 스레드에서 OpenAIService.generate_cartoon 호출 → 성공 시 result_image_url 저장 및 PostService.create_post로 자동 게시, NotificationService.CARTOON_SUCCESS 전송.
3. 실패 시 status=failed, error_message 저장, NotificationService.CARTOON_FAILED 전송.
4. 취소 요청은 status를 canceling으로만 변경(Cloud Function이 실제 중단 처리).

## 공통 규약

- 시간/타임존: UTC 고정. Firestore Timestamp는 DateTimeUtils.for_firestore/ to_timestamp_ms로 상호 변환.
- 에러 포맷: { error_code, message?, details? } (전역 ValidationError 핸들러 존재).
- 인증: flask_jwt_extended 기반. 대부분 엔드포인트에 @jwt_required 적용.

## 1) comments

### 엔드포인트

- POST /api/posts/{post_id}/comments — 댓글 생성(201)
- GET /api/posts/{post_id}/comments — 댓글 목록 조회(페이징)
- DELETE /api/comments/{comment_id} — 댓글 삭제(작성자만, 204)
- POST /api/comments/{comment_id}/like — 댓글 좋아요 토글

### 요청/스키마

- CommentCreateSchema: { text: string(1~1000) }

### 응답/출력

- 댓글 객체(CommentResponse): { comment_id, post_id, author{ user_id,nickname,profile_image_url }, text, like_count, created_at, is_liked? }
- 목록: { comments: CommentResponse[], next_cursor } — next_cursor는 마지막 comment_id.

### 오류 케이스

- POST: 400 VALIDATION_ERROR | 404 RESOURCE_NOT_FOUND(작성자/게시글 없음) | 500 COMMENT_CREATION_FAILED
- GET: 500 INTERNAL_SERVER_ERROR
- DELETE: 403 FORBIDDEN | 404 NOT_FOUND
- LIKE 토글: 404 COMMENT_NOT_FOUND | 500 LIKE_TOGGLE_FAILED

### 저장/비즈니스 로직
### 데이터 타입 요약
- CommentCreateSchema: { text: string(1..1000) }
- CommentResponse: { comment_id: UUID, post_id: UUID, author: { user_id: UUID, nickname: string, profile_image_url: URL|null }, text: string, like_count: int, created_at: ISO8601, is_liked?: boolean }

1. Firestore: comments, posts, users, likes 사용. comment_id=UUID. likes 문서 키: comment_{user_id}_{comment_id}.
2. 생성: 트랜잭션으로 comments set + posts.comment_count 증가. 작성자≠게시글 작성자면 NotificationType.COMMENT 알림 생성.
3. 멘션(@nickname) 추출 → 해당 사용자들에게 NotificationType.MENTION 발송(닉네임 기반 users 조회).
4. 좋아요 토글: likes 문서 upsert/delete + comments.like_count 증감. 다른 사용자의 댓글을 좋아요하면 COMMENT_LIKE 알림.

## 2) notifications

### 엔드포인트

- GET /api/notifications?limit&cursor — 내 알림 목록 조회(페이징)
- POST /api/notifications/{notification_id}/ack — 알림 읽음 처리
- GET /api/notifications/unread-count — 읽지 않은 알림 개수 조회

### 출력 포맷(목록)

- 아이템: { id, type, title, message, created_at, deeplink, read } — type별 title/deeplink 규칙 반영.

deeplink 규칙: CARTOON* → app://cartoon-jobs/{target_id}, COMMENT/POST_LIKE/MENTION → app://posts/{target_id}, COMMENT_LIKE → app://comments/{target_id}, PET_CARE* → app://pet-care/dashboard?petId={pet_id|recipient_id}&date=YYYY-MM-DD&tab={record_type|weight}.

### 오류 케이스

- 목록: 500 FETCH_FAILED
- ack: 404 NOT_FOUND_OR_FORBIDDEN | 500 ACK_FAILED
- unread-count: 500 FETCH_FAILED

### 저장/비즈니스 로직(서비스)
### 데이터 타입 요약
- Notification item: { id: UUID, type: string(enum), title: string, message: string, created_at: ISO8601, deeplink: string(app://...), read: boolean }
- List Response: { notifications: array<item>, next_cursor?: string, has_more?: boolean }
- Ack Response: { message: string } | 204 No Content(선택 구현 시)

1. create_notification: recipient 검증 및 per-user preferences(types, mode) 반영. in-app 저장 + 필요 시 FCM 푸시 전송.
2. list_notifications: recipient_id 기준 내림차순, limit+1로 has_more 판단, created_at ISO 문자열 변환 보정.
3. ack_notification: 소유자 일치 시 is_read=true 업데이트.
4. get_unread_count: 쿼리 count() 사용(가능 시), 없으면 stream으로 합산.

## 3) pet_care/records

### 엔드포인트

- POST /api/pet-care/{pet_id}/records — 케어 기록 생성(멱등, request_id)
- GET /api/pet-care/{pet_id}/records — 케어 기록 유연 조회(기간/타입/페이징)
- GET /api/pet-care/{pet_id}/records/{record_type} — 특정 타입 기록 조회(페이징)
- GET /api/pet-care/{pet_id}/records/legacy — 구버전 호환 조회(Deprecated)
- PATCH /api/pet-care/{pet_id}/records/{log_id} — 케어 기록 일부 수정
- DELETE /api/pet-care/{pet_id}/records/{log_id} — 케어 기록 삭제

### 요청/스키마

- CareRecordCreate: { record_type∈[weight,water,activity,meal,bcs], timestamp(ms), data(타입별), notes?, request_id? } — 타입별 검증 포함.
- RecordsQuery: { date or (start_date,end_date), record_types[], grouped(bool), limit(1~100,default 50), cursor, sort(timestamp_asc|timestamp_desc) } — record_types는 콤마 문자열 가능.
- RecordTypeQuery: { date or (start_date,end_date), limit(default 50), cursor }
- CareRecordUpdate: { data?, notes?, timestamp? } — 서비스에서 타입별 엄격 검증.

### 응답/출력

- POST 생성 응답: 생성 문서(dict). timestamp는 서버 내부 UTC datetime(직렬화 시 ISO 문자열로 표현 가능).
- 유연 조회: { records: [{ log_id,pet_id,record_type,timestamp(ms),data,notes,searchDate }...], meta{ total_count, limit, has_more, next_cursor }, grouped? }
- 타입 조회: { records:[...timestamp(ms)...], meta{ record_type,total_count,limit,has_more,next_cursor } }
- legacy(date): DailyRecordsResponseSchema { weight[], water[], activity[], meal[], bcs[] } (각 항목은 레코드 dict).
- legacy(range): { YYYY-MM-DD: { weight[], water[], activity[], meal[], bcs[] }, ... }

### 오류 케이스

- POST: 400 VALIDATION_ERROR | 500 RECORD_CREATION_FAILED
- GET(records): 400 VALIDATION_ERROR | 500 FETCH_FAILED
- GET(by type): 400 INVALID_RECORD_TYPE/VALIDATION_ERROR | 500 FETCH_FAILED
- legacy: 400 MISSING_PARAMETERS/INVALID_DATE_FORMAT | 500 FETCH_FAILED
- PATCH: 400 VALIDATION_ERROR | 404 NOT_FOUND | 403 FORBIDDEN | 500 UPDATE_FAILED
- DELETE: 404 NOT_FOUND | 403 FORBIDDEN | 500 DELETE_FAILED

### 저장/조회 로직 및 인덱스
### 데이터 타입 요약
- CareRecordCreate: { record_type: string(enum: weight|water|activity|meal|bcs), timestamp: timestamp(ms), data: object, notes?: string, request_id?: string }
- RecordsQuery: { date?: string(YYYY-MM-DD), start_date?: string, end_date?: string, record_types?: array<string>|string(csv), grouped?: boolean, limit?: int(1..100), cursor?: string, sort?: string(timestamp_asc|timestamp_desc) }
- Records Response: { records: array<{ log_id: UUID, pet_id: UUID, record_type: string, timestamp: timestamp(ms), data: object, notes?: string, searchDate: string(YYYY-MM-DD) }>, meta: { total_count?: int, limit: int, has_more: boolean, next_cursor?: string }, grouped?: object }

1. 콜렉션: pet_care_logs. 문서 키: log_id(request_id 멱등키 또는 UUID). 필드: { log_id, pet_id, record_type, timestamp(UTC datetime), searchDate('YYYY-MM-DD'), data, notes }.
2. 생성: DateTimeUtils.from_timestamp_ms로 UTC 변환 → searchDate 생성 → set(merge=True)로 멱등 upsert.
3. 조회: pet_id + (searchDate eq/range), record_type in(<=10) 조합. timestamp asc/desc 정렬. cursor 기반 start_after, limit+1로 has_more 판단.
4. 권장 인덱스: (pet_id, searchDate, timestamp) 복합 색인.

## **pet_care/settings**

### 엔드포인트

- GET /api/pet-care/{pet_id}/settings
    - jwt_required — 지정 펫의 케어 설정 조회
    - 응답: PetCareSettingsSchema
    - 오류: 404 SETTINGS_NOT_FOUND | 500 FETCH_FAILED
- PUT /api/pet-care/{pet_id}/settings
    - jwt_required — 지정 펫의 케어 설정 갱신
    - 본문: PetCareSettingsSchema(partial=True)
    - 응답: PetCareSettingsSchema
    - 오류: 400 VALIDATION_ERROR|NO_DATA | 404 SETTINGS_NOT_FOUND | 500 UPDATE_FAILED

### 스키마(요청/응답)

- PetCareSettingsSchema
    - goalWeight: float [0.1..200.0]
    - waterBowlCapacity: int [1..5000]
    - waterIncrementAmount: int [1..1000]
    - goalActivityMinutes: int [0..1440]
    - activityIncrementMinutes: int [1..180]
    - goalMealCount: int [1..10]
    - mealIncrementCount: int [1..5]
    - dump_only: pet_id, updated_at

### 데이터 타입 요약
- PetCareSettingsSchema(updated_at): ISO8601(UTC)

### 저장/비즈니스 로직

- 컬렉션: pet_settings (doc ID = pet_id; pets와 1:1)
- 초기 생성(트랜잭션): create_initial_settings_transactional
    - BreedService.get_breed_ideal_weight(breed, gender) → goalWeight
    - waterBowlCapacity = round(current_weight * 60), waterIncrement ≈ 20% (최소 1)
    - created_at/updated_at: DateTimeUtils.now → for_firestore로 변환 저장
- 조회/수정: get_settings, update_settings
    - 존재 확인 + updated_at 갱신
- 의존: Firestore, BreedService, DateTimeUtils

## **pets**

### 엔드포인트

- POST /api/pets/
    - jwt_required
    - 본문: PetRegistrationSchema
    - 응답: PetProfileResponseSchema
    - 오류: 400 VALIDATION_ERROR, 500 PET_REGISTRATION_FAILED
- GET /api/pets/{pet_id}
    - jwt_required — 소유자 전용 Full Profile 조회
    - 오류: 403 FORBIDDEN_OR_NOT_FOUND, 500 FETCH_FAILED
- PATCH /api/pets/{pet_id}
    - jwt_required — 펫 프로필 부분 수정
    - 본문: PetUpdateSchema(partial update)
    - 응답: PetProfileResponseSchema
    - 오류: 400 VALIDATION_ERROR, 403 UPDATE_FAILED_FORBIDDEN, 500 INTERNAL_SERVER_ERROR
- GET /api/pets/public-profile/{pet_id}
    - jwt_required(optional) — 공개 프로필 조회
    - 응답: PetPublicProfileResponseSchema
    - 오류: 404 PET_NOT_FOUND, 500 FETCH_FAILED
- POST /api/pets/{pet_id}/nose-print
    - jwt_required — 비문 등록/인증
    - 본문: BiometricAnalysisRequestSchema(file_path)
    - 응답: { status: SUCCESS | ALREADY_VERIFIED | DUPLICATE | INVALID_IMAGE | ERROR, ... }
    - 오류: 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 ERROR
- POST /api/pets/{pet_id}/eye-analysis
    - jwt_required — 안구 이미지 분석
    - 본문: BiometricAnalysisRequestSchema(file_path)
    - 응답: EyeAnalysisResponseSchema { analysis_id, disease_name, probability }
    - 오류: 400 VALIDATION_ERROR, 403 FORBIDDEN, 500 ANALYSIS_FAILED/INTERNAL_SERVER_ERROR

### 스키마(요청/응답)

- PetRegistrationSchema: name(1..20), gender(PetGender Enum), breed(존재 검사), birthdate(%Y-%m-%d), current_weight(0.1..200.0), fur_color?, health_concerns?
- PetUpdateSchema: name?, fur_color?, health_concerns?
- BiometricAnalysisRequestSchema: file_path(required)
- PetProfileResponseSchema(소유자용): pet_id, user_id, name, gender, breed, birthdate, initial_weight, fur_color?, health_concerns[], is_verified, nose_print_url?, faiss_id?
- PetPublicProfileResponseSchema(공개용): 민감 정보 제외
- EyeAnalysisResponseSchema: analysis_id, disease_name, probability

### 데이터 타입 요약
- PetProfileResponseSchema: birthdate: string(YYYY-MM-DD), initial_weight: float, is_verified: boolean, nose_print_url: URL|null
- PetPublicProfileResponseSchema: birthdate: string(YYYY-MM-DD), initial_weight: float, is_verified: boolean
- EyeAnalysisResponseSchema: { analysis_id: UUID|null, disease_name: string, probability: float }

### 저장/비즈니스 로직

- 컬렉션: pets
    - 등록(register_pet): Firestore 트랜잭션
        - pets 문서 생성(asdict Pet → DateTimeUtils.for_firestore)
        - 같은 트랜잭션으로 pet_settings 초기화(create_initial_settings_transactional)
- Nose print
    - 권한/소유 확인 → nose_pipeline.process_image(storage_service, file_path)
    - SUCCESS면 트랜잭션으로 pets 업데이트(is_verified, nose_print_url(public), faiss_id), 인덱스에 vector 반영
    - 실패면 상태 그대로 반환(DUPLICATE/INVALID_IMAGE/ERROR)
- Eye analysis
    - Storage에서 download_as_bytes(file_path) → eye_analyzer.predict
    - 가능하면 public url 생성(실패해도 분석 결과엔 영향 없음)
    - 결과를 analysis_history에 save_analysis_result
- 의존: Firestore, StorageService, PetCareSettingService, NosePrintPipeline, EyeAnalyzer, DateTimeUtils, BreedService(스키마 검증 시)

## **posts**

### 엔드포인트

- POST /api/posts/
    - jwt_required
    - 본문: PostCreateSchema(text, file_paths)
    - 응답: PostResponseSchema
    - 오류: 400 VALIDATION_ERROR, 404 RESOURCE_NOT_FOUND(작성자/반려동물 없음), 500 POST_CREATION_FAILED
- GET /api/posts/?limit&cursor
    - jwt_required(optional) — 피드 조회(페이징)
    - 응답: { posts: PostResponseSchema[], next_cursor }
- GET /api/posts/{post_id}
    - jwt_required(optional) — 게시글 상세(+is_liked)
    - 응답: PostResponseSchema(+ is_liked)
    - 오류: 404 POST_NOT_FOUND
- PATCH /api/posts/{post_id}
    - jwt_required — 게시글 수정
    - 본문: PostUpdateSchema(text)
    - 오류: 400 VALIDATION_ERROR, 403 FORBIDDEN, 404 POST_NOT_FOUND
- DELETE /api/posts/{post_id}
    - jwt_required — 게시글 삭제(스토리지/문서)
    - 오류: 403 FORBIDDEN, 404 POST_NOT_FOUND
- POST /api/posts/{post_id}/like
    - jwt_required — 좋아요 토글(트랜잭션)
    - 알림: 좋아요 생성 시, 본인 글이 아니면 NotificationType.POST_LIKE 발송
    - 오류: 404 POST_NOT_FOUND, 500 LIKE_TOGGLE_FAILED
- GET /api/posts/users/{author_id}/posts?limit&cursor
    - jwt_required(optional)
    - 응답: { posts, next_cursor }

### 스키마(요청/응답)

- Author: user_id, nickname, profile_image_url?
- PetInfo: pet_id, name, breed, birthdate(DateTime)
- PostCreateSchema: text(1..2000), file_paths(최소 1)
- PostUpdateSchema: text(1..2000)
- PostResponseSchema: post_id, author, pet, image_urls[], text, like_count, comment_count, created_at, updated_at, is_liked?

### 저장/비즈니스 로직
### 데이터 타입 요약
- PostCreateSchema: { text: string(1..2000), file_paths: array<URL>[min 1] }
- PostResponseSchema: { post_id: UUID, author: { user_id: UUID, nickname: string, profile_image_url: URL|null }, pet: { pet_id: UUID, name: string, breed: string, birthdate: string(YYYY-MM-DD) }, image_urls: array<URL>, text: string, like_count: int, comment_count: int, created_at: ISO8601, updated_at: ISO8601, is_liked?: boolean }

- 컬렉션: posts, users, pets, likes
- 생성(create_post)
    - users/{user_id}와 pets.where(user_id==...).limit(1) 확인 후 Author/PetInfo 구성
    - image_urls ← file_paths 그대로 저장
    - DateTimeUtils.for_firestore(asdict(Post))로 저장
- 피드 조회
    - created_at desc 정렬, cursor(문서 id) 기반 페이징
    - 로그인 사용자면 likes에서 **name** in batched(≤30)로 is_liked 도출
- 상세 조회
    - 단건 + is_liked
- 수정
    - 소유자 확인 → text, updated_at 갱신
- 삭제
    - 소유자 확인 → image_urls의 Firebase Storage URL에서 file_path 추출 후 blob.delete → post 삭제
- 좋아요 토글
    - 트랜잭션으로 likes 생성/삭제 + posts.like_count 증감
    - 생성 시 상대에게 POST_LIKE 알림
- 인덱스/주의
    - 복합 인덱스: (created_at desc), (author.user_id, created_at desc) 필요
    - update_post는 datetime.utcnow 사용(UTC 권장 규칙과의 일관성 확인 필요)

## uploads

### Endpoints

- POST /api/uploads/url (jwt_required): 업로드용 Pre-signed URL 발급
- POST /api/uploads/finalize-cartoon (jwt_required): 업로드된 파일 공개 전환 및 URL 반환

### Request/Response

- POST /url 요청(JSON): { upload_type, filename, content_type }
- POST /url 응답: { upload_url, file_path }
- POST /finalize-cartoon 요청(JSON): { file_path }
- POST /finalize-cartoon 응답: { public_url }

### Validation & Errors

- INVALID_PARAMETERS(400): 필수 파라미터 누락/형식 오류 (upload_type, filename, content_type)
- INVALID_UPLOAD_TYPE(400): 지원하지 않는 upload_type
- VALIDATION_ERROR(400): file_path 스키마 검증 실패
- FILE_NOT_FOUND(404): Storage에 해당 파일 없음
- URL_GENERATION_FAILED/INTERNAL_SERVER_ERROR(500): 서버 내부 오류

### Persistence & Services

- StorageService.generate_upload_url(user_id, upload_type, filename, content_type): 서명 URL 발급 및 GCS 경로(file_path) 지정
- StorageService.make_public_and_get_url(file_path): 파일 공개 전환 및 public URL 반환

Firestore 저장 없음(업로드 경로/URL만 발급/전환).

### 데이터 타입 요약
- /url Request: { upload_type: string(enum), filename: string, content_type: string }
- /url Response: { upload_url: URL, file_path: string }
- /finalize-cartoon Request: { file_path: string }
- /finalize-cartoon Response: { public_url: URL }

## users

### Endpoints

- GET /api/users/{user_id} (optional auth): 공개 프로필 + post_count
- PATCH /api/users/me/profile-image (jwt_required): file_path 기반 프로필 이미지 갱신
- DELETE /api/users/me (jwt_required): 계정 삭제(Firebase Auth), Firestore 데이터는 확장에 의해 처리
- GET /api/users/me/notification-preferences (jwt_required): 알림 개인 설정 조회
- PATCH /api/users/me/notification-preferences (jwt_required): 알림 개인 설정 업데이트
- POST /api/users/me/fcm-token (jwt_required): FCM 토큰 등록/업데이트
- GET /api/users/{user_id}/summary (optional auth): 공개 사용자 요약 + (pet_id 지정 시) 반려견 요약(age_months 포함)
- GET /api/users/me/summary (optional auth): 현재 사용자/선택 반려견/해당 설정 요약
// 신규: 선택 펫 영속화 API
- GET /api/users/me/selected-pet (jwt_required): 현재 선택된 펫 조회
- PATCH /api/users/me/selected-pet (jwt_required): 현재 선택된 펫 설정(멱등)

### Schemas

- UserPublicResponseSchema: user_id, nickname, profile_image_url, post_count
- FCMTokenSchema: fcm_token(required)
- NotificationPreferencesSchema: mode?, types{ [NotificationType string]: bool }?
// 신규
- SelectedPetUpdateSchema: { pet_id: string(uuid) }

### Validation & Errors

- USER_NOT_FOUND(404): 사용자 미존재
- VALIDATION_ERROR(400): 스키마 검증 실패(FCM 토큰/알림 설정 등)
- PROFILE_FETCH_FAILED/INTERNAL_SERVER_ERROR/UPDATE_FAILED/ACCOUNT_DELETION_FAILED/SUMMARY_FETCH_FAILED(500)
// 신규: selected-pet 전용 규칙(클라 표준 에러 스키마 적용)
- GET /api/users/me/selected-pet
    - 200 { pet_id, name?, profile_image_url?, updated_at? }
    - 204 No Content: 선택 펫 없음
    - 403 { message: "선택된 반려동물에 대한 소유 권한이 없습니다." } (기록은 있으나 소유권 상실)
    - 404 { message: "선택된 반려동물을 찾을 수 없습니다." } (기록은 있으나 펫 삭제/부재)
- PATCH /api/users/me/selected-pet
    - 200 { pet_id }
    - 400 { message: "유효하지 않은 요청 본문입니다.", errors: { pet_id: ["유효한 UUID가 아닙니다."] } }
    - 403 { message: "해당 반려동물을 선택할 권한이 없습니다." } (존재하지만 타 사용자 소유)
    - 404 { message: "해당 반려동물을 찾을 수 없습니다." }
    - 401은 공통 규칙에 따라 토큰 리프레시 시도

### Persistence & Services

- Firestore: users 컬렉션(프로필, fcm_token, notification_preferences 저장)
- PostService.count_posts_by_user_id: 공개 프로필 응답에 post_count 제공
- StorageService: profile_image file_path를 public URL로 전환 후 users.profile_image_url 업데이트
- Firebase Auth: delete_user(user_id)로 계정 삭제(이미 삭제된 경우도 예외 없이 통과 처리)

요약 엔드포인트: PetService/PetCareSettingService 연동, DateTimeUtils.calculate_age_months 사용.

// 신규: 선택 펫 영속화
- Firestore: user_selected_pet (doc id = user_id)
    - Fields: { user_id: string, pet_id: string|null, updated_at: Firestore Timestamp(UTC) }
    - GET: 문서가 없거나 pet_id가 null이면 204 No Content
    - PATCH: set(upsert)로 멱등 저장, Last-Write-Wins
    - 응답 시 updated_at은 ISO8601(UTC)로 직렬화

### 데이터 타입 요약
- GET /users/me Response(200): { pet_id: UUID, name?: string, profile_image_url?: URL|null, updated_at?: ISO8601 }
- GET /users/me Response(204): No Content
- PATCH /users/me Request: { pet_id: UUID }
- PATCH /users/me Response(200): { pet_id: UUID }