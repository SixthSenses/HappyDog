# HappyDog API - Postman 환경 설정 가이드

## 📋 생성된 환경

### 1. **HappyDog - Development** (개발 환경)
- **Environment ID**: `39a9f7c5-634f-438c-8f38-e34aacddb473`
- **Base URL**: `http://localhost:5000` (전체 경로 포함)
- **용도**: 로컬 개발 및 테스트

### 2. **HappyDog - Production** (운영 환경)
- **Environment ID**: `d6e3970f-507a-4fa7-9eb7-9b00904de19e`
- **Base URL**: `https://api.happydog.com` (전체 경로 포함)
- **용도**: 실제 서비스 테스트

---

## 🔑 환경 변수 목록

| 변수명 | 타입 | 기본값 | 설명 |
|--------|------|--------|------|
| `base_url` | default | `http://localhost:5000` (Dev)<br>`https://api.happydog.com` (Prod) | Backend API 기본 URL (전체 경로) |
| `jwt_token` | secret | (빈 값) | JWT 인증 토큰<br>로그인 후 자동 저장 |
| `user_id` | default | (빈 값) | 현재 로그인한 사용자 ID |
| `pet_id` | default | (빈 값) | 테스트용 반려동물 ID |
| `post_id` | default | (빈 값) | 테스트용 게시글 ID |
| `job_id` | default | (빈 값) | 테스트용 만화 작업 ID |
| `file_path` | default | (빈 값) | 업로드된 파일 경로 |
| `idempotency_key` | default | `{{$guid}}` | 멱등성 키 (자동 생성) |

---

## 🚀 사용 방법

### 1. 환경 선택
Postman 우측 상단에서 환경을 선택합니다:
- 로컬 테스트: **HappyDog - Development**
- 운영 테스트: **HappyDog - Production**

### 2. 인증 토큰 설정

#### 방법 1: 자동 설정 (권장)
로그인 API 호출 후 **Tests** 탭에 다음 스크립트 추가:

```javascript
// POST /api/auth/social 응답 처리
const response = pm.response.json();

if (response.access_token) {
    pm.environment.set("jwt_token", response.access_token);
    pm.environment.set("user_id", response.user_id);
    console.log("✅ JWT 토큰 자동 저장 완료");
}
```

#### 방법 2: 수동 설정
1. Postman 우측 상단 **눈 아이콘** 클릭
2. **HappyDog - Development** 선택
3. `jwt_token` 변수에 값 입력
4. **Save** 클릭

### 3. API 요청에서 사용

#### URL 구성
```
{{base_url}}/api/cartoon-jobs
```
실제 URL: `http://localhost:5000/api/cartoon-jobs`

**참고:** OpenAPI 스펙의 `servers.url`에 `/api` prefix가 제거되어 있으므로, 
Swagger UI에서는 자동으로 `base_url + path`가 조합됩니다.

#### Authorization 헤더
```
Bearer {{jwt_token}}
```

#### 멱등성 헤더 (POST/PUT/DELETE)
```
X-Idempotency-Key: {{idempotency_key}}
```

---

## 📝 테스트 시나리오 예시

### 시나리오 1: 사용자 인증 플로우

```
1. POST /api/auth/social
   → jwt_token, user_id 자동 저장

2. GET /api/users/me
   → Authorization: Bearer {{jwt_token}}
   
3. GET /api/pets/profile?view=owner
   → 내 반려동물 목록 조회
   → pet_id 저장
```

### 시나리오 2: 만화 생성 플로우

```
1. POST /api/uploads/url
   Body: {
     "upload_type": "cartoon_source",
     "filename": "dog.jpg",
     "content_type": "image/jpeg"
   }
   → Pre-signed URL 받기
   
2. PUT {presigned_url}
   → 실제 이미지 업로드
   → file_path 저장
   
3. POST /api/cartoon-jobs
   Headers: {
     "X-Idempotency-Key": "{{idempotency_key}}"
   }
   Body: {
     "file_paths": ["{{file_path}}"],
     "user_text": "귀여운 만화로 만들어주세요"
   }
   → job_id 저장
   
4. GET /api/cartoon-jobs/{{job_id}}
   → 작업 상태 조회
```

### 시나리오 3: 게시글 작성

```
1. POST /api/posts
   Headers: {
     "X-Idempotency-Key": "{{idempotency_key}}"
   }
   Body: {
     "text": "오늘 산책 다녀왔어요!",
     "file_paths": ["{image_url}"],
     "pet_tags": ["{{pet_id}}"]
   }
   → post_id 저장
   
2. GET /api/posts/{{post_id}}
   → 게시글 확인
```

---

## 🔧 고급 설정

### Tests 스크립트 예시

#### 1. 응답에서 ID 자동 추출
```javascript
const response = pm.response.json();

// 만화 작업 ID 저장
if (response.job_id) {
    pm.environment.set("job_id", response.job_id);
}

// 게시글 ID 저장
if (response.post_id) {
    pm.environment.set("post_id", response.post_id);
}

// 파일 경로 저장
if (response.file_path) {
    pm.environment.set("file_path", response.file_path);
}
```

#### 2. 멱등성 키 갱신
```javascript
// 요청 성공 시 새로운 멱등성 키 생성
if (pm.response.code === 200 || pm.response.code === 202) {
    pm.environment.set("idempotency_key", pm.variables.replaceIn("{{$guid}}"));
}
```

#### 3. 에러 처리
```javascript
if (pm.response.code >= 400) {
    console.error("❌ API Error:", pm.response.json());
    
    // 401 Unauthorized - 토큰 만료
    if (pm.response.code === 401) {
        console.warn("⚠️ JWT 토큰이 만료되었습니다. 다시 로그인하세요.");
    }
}
```

---

## 📊 환경 변수 값 예시

### Development (개발)
```json
{
  "base_url": "http://localhost:5000",
  "api_prefix": "/api",
  "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "user123",
  "pet_id": "pet456",
  "post_id": "post789",
  "job_id": "job_abc123",
  "file_path": "cartoon_sources/user123/abc123.jpg",
  "idempotency_key": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Production (운영)
```json
{
  "base_url": "https://api.happydog.com",
  "api_prefix": "/api",
  "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "prod_user456",
  "pet_id": "prod_pet789",
  "post_id": "prod_post012",
  "job_id": "prod_job_xyz789",
  "file_path": "cartoon_sources/prod_user456/xyz789.jpg",
  "idempotency_key": "660f9511-f3ac-52e5-b827-557766551111"
}
```

---

## ⚠️ 주의사항

### 1. JWT 토큰 보안
- `jwt_token`은 **secret** 타입으로 설정되어 자동으로 마스킹됩니다
- 토큰을 절대 Git에 커밋하지 마세요
- 팀원과 환경을 공유할 때는 토큰 값을 비워두세요

### 2. 멱등성 키
- POST/PUT/PATCH/DELETE 요청 시 항상 `X-Idempotency-Key` 헤더 포함
- `{{idempotency_key}}`는 매 요청마다 새로운 GUID 생성
- 재시도가 필요한 경우 같은 키를 사용하세요

### 3. 환경 분리
- **절대** Development 환경에서 Production 데이터를 수정하지 마세요
- Production 환경은 읽기 전용 테스트만 권장

### 4. 파일 경로
- `file_path`는 Firebase Storage의 상대 경로입니다
- 전체 URL이 필요한 경우 API가 자동으로 변환합니다

---

## 🔗 관련 링크

- **API 문서**: Swagger UI (로컬 실행 시 확인)
- **OpenAPI 스펙**: `openapi_pretty.json`
- **Backend 저장소**: `pet_project_backend/`
- **Postman 워크스페이스**: 박정호's Workspace

---

## 💡 팁

### 빠른 테스트를 위한 Pre-request Script
Collection 또는 Folder 레벨에 추가:

```javascript
// Authorization 헤더 자동 추가
if (pm.environment.get("jwt_token")) {
    pm.request.headers.add({
        key: "Authorization",
        value: "Bearer " + pm.environment.get("jwt_token")
    });
}

// Idempotency-Key 헤더 자동 추가 (POST/PUT/DELETE)
const method = pm.request.method;
if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    pm.request.headers.add({
        key: "X-Idempotency-Key",
        value: pm.environment.get("idempotency_key")
    });
}
```

### 환경 변수 디버깅
Console에서 현재 값 확인:
```javascript
console.log("Base URL:", pm.environment.get("base_url"));
console.log("JWT Token:", pm.environment.get("jwt_token") ? "설정됨" : "없음");
console.log("User ID:", pm.environment.get("user_id"));
```

---

**생성일**: 2025-10-11  
**버전**: 1.0.0  
**작성자**: AI Assistant
