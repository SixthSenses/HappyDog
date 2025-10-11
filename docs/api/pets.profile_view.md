# 뷰 기반 반려동물 프로필 조회 가이드

- Endpoint: `GET /api/pets/profile`
- 인증: 선택적(`Authorization: Bearer <token>`). 단, 타인 프로필 조회 시 인증 필요.
- 스키마: `ResponseSchema[200]: PetViewBasedResponseSchema`

## 뷰(view) 타입과 접근 규칙
- `mypage`: 소유자만 조회 가능(본인 토큰 필요)
- `petcare`: 소유자만 조회 가능(본인 토큰 필요)
- `social`: 공개용. 타인 프로필을 조회하려면 인증 필요

정책 요약(PetAccessPolicy):
- `target_user_id == current_user_id`이면 모두 허용
- 타인 프로필 접근 시:
  - 미인증이면 거부(`AUTHENTICATION_REQUIRED` → 400 VALIDATION_ERROR)
  - `mypage`/`petcare`는 거부(403 FORBIDDEN)
  - `social`만 허용

## 쿼리 파라미터
- `user_id` (optional): 조회 대상 사용자 ID. 미지정 시 현재 사용자로 간주
- `view` (optional): `mypage` | `petcare` | `social` (기본값: `mypage`)

## 응답 필드(스키마 요약)
- 공통(base): `pet_id`, `name`, `profile_image_url`, `is_verified`
- 신원(identity): `birthdate(YYYY-MM-DD)`, `gender(FEMALE|MALE)`, `breed`
- social 전용: `age_months`, `post_count`

Note: `petcare`는 현재 공통(base) 필드만 포함됩니다.

---

## 사용 예시

### 1) 내 프로필 - 마이페이지 뷰(mypage)
- 설명: 본인 프로필 상세(신원 포함)
- 요구: 본인 토큰 필요
- 요청
```cmd
curl -X GET "http://127.0.0.1:5000/api/pets/profile?view=mypage" ^
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```
- 예시 응답(200)
```json
{
  "pet_id": "pet_123",
  "name": "바둑이",
  "profile_image_url": "https://storage.googleapis.com/.../profile.jpg",
  "is_verified": true,
  "birthdate": "2023-05-10",
  "gender": "MALE",
  "breed": "Jindo"
}
```

### 2) 내 프로필 - 펫케어 뷰(petcare)
- 설명: 케어 화면용 최소 정보(공통 필드만)
- 요구: 본인 토큰 필요
- 요청
```cmd
curl -X GET "http://127.0.0.1:5000/api/pets/profile?view=petcare" ^
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```
- 예시 응답(200)
```json
{
  "pet_id": "pet_123",
  "name": "바둑이",
  "profile_image_url": null,
  "is_verified": true
}
```

### 3) 타인 프로필 - 소셜 뷰(social)
- 설명: 공개용 정보 + 파생 지표(나이 개월, 게시물 수)
- 요구: 인증 필요(타인 접근 시)
- 요청
```cmd
curl -X GET "http://127.0.0.1:5000/api/pets/profile?user_id=user_456&view=social" ^
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```
- 예시 응답(200)
```json
{
  "pet_id": "pet_456",
  "name": "초코",
  "profile_image_url": "https://storage.googleapis.com/.../choco.jpg",
  "is_verified": false,
  "birthdate": "2022-11-02",
  "gender": "FEMALE",
  "breed": "Poodle",
  "age_months": 22,
  "post_count": 17
}
```

---

## 오류 응답 예시

### 잘못된 view 값
- 요청: `view=home` 등 허용 외 값
- 응답: 400 VALIDATION_ERROR
```json
{
  "error_code": "VALIDATION_ERROR",
  "category": "CLIENT",
  "retriable": false,
  "message": "view는 mypage, petcare, social 중 하나여야 합니다.",
  "details": {}
}
```

### 미인증으로 타인 프로필 접근
- 요청: `?user_id=user_456&view=social` (Authorization 헤더 없음)
- 응답: 400 VALIDATION_ERROR
```json
{
  "error_code": "VALIDATION_ERROR",
  "category": "CLIENT",
  "retriable": false,
  "message": "인증이 필요합니다.",
  "details": {}
}
```

### 타인 프로필에 mypage/petcare 요청
- 응답: 403 FORBIDDEN
```json
{
  "error_code": "FORBIDDEN",
  "category": "CLIENT",
  "retriable": false,
  "message": "접근이 허용되지 않습니다.",
  "details": {}
}
```

### 등록된 반려동물이 없는 경우
- 응답: 404 NOT_FOUND
```json
{
  "error_code": "NOT_FOUND",
  "category": "CLIENT",
  "retriable": false,
  "message": "등록된 반려동물이 없습니다.",
  "details": {}
}
```

---

## 통합 팁
- 기본값: `view` 미지정 시 `mypage`
- 프론트 측 분기 추천
  - 마이페이지/펫케어 화면: `view=mypage|petcare` (항상 본인 토큰 포함)
  - 프로필 공개 화면(타인): `user_id=<상대>` + `view=social` (토큰 있음이 안전)
- 스키마 일관성
  - 날짜: `birthdate`는 ISO `YYYY-MM-DD`
  - 성별: `gender`는 enum(`FEMALE`/`MALE`)