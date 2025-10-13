# OpenAPI Spec `/api/api` 중복 문제 해결 보고서

**일시**: 2025-10-11  
**문제**: Swagger UI에서 API 경로가 `/api/api/...`로 중복되는 현상  
**상태**: ✅ 해결 완료

---

## 🐛 문제 발견

### 증상
Swagger UI 또는 Postman에서 API를 테스트할 때 다음과 같은 URL이 생성됨:

```
❌ 잘못된 URL:
http://localhost:5000/api/api/auth/google/authorize
                        ^^^^^^^^  /api가 두 번!
```

### 원인 분석

OpenAPI 3.0 스펙에서 최종 URL은 다음과 같이 조합됩니다:
```
최종 URL = {servers[].url} + {paths.<path>}
```

**문제가 있던 구조:**
```json
{
  "servers": [
    {
      "url": "http://localhost:5000/api"  // ← /api 포함
    }
  ],
  "paths": {
    "/api/auth/google/authorize": {}      // ← /api 포함
  }
}
```

**결과:**
```
http://localhost:5000/api + /api/auth/google/authorize
= http://localhost:5000/api/api/auth/google/authorize  ❌
```

---

## ✅ 해결 방법

### 수정한 파일
`pet_project_backend/scripts/swagger_build.py` (Line 466-467)

### 변경 내용

**Before:**
```python
spec['servers'] = [
    {'url': 'http://localhost:5000/api', 'description': 'Development'},
    {'url': 'https://api.happydog.com/api', 'description': 'Production'}
]
```

**After:**
```python
spec['servers'] = [
    {'url': 'http://localhost:5000', 'description': 'Development'},
    {'url': 'https://api.happydog.com', 'description': 'Production'}
]
```

### 수정 후 URL 구조

```json
{
  "servers": [
    {
      "url": "http://localhost:5000"       // ← /api 제거
    }
  ],
  "paths": {
    "/api/auth/google/authorize": {}       // ← /api 유지
  }
}
```

**결과:**
```
http://localhost:5000 + /api/auth/google/authorize
= http://localhost:5000/api/auth/google/authorize  ✅
```

---

## 🔄 영향 받는 파일

### 1. OpenAPI 스펙 파일
- ✅ `openapi.json` - 재생성 완료
- ✅ `openapi_pretty.json` - 재생성 완료

### 2. Postman 환경 변수
- ✅ **HappyDog - Development**
  - `base_url`: `http://localhost:5000` (변경 없음, `/api` prefix 제거)
  - `api_prefix` 변수 제거 (더 이상 필요 없음)

- ✅ **HappyDog - Production**
  - `base_url`: `https://api.happydog.com` (변경 없음, `/api` prefix 제거)
  - `api_prefix` 변수 제거

### 3. 문서
- ✅ `docs/POSTMAN_ENVIRONMENT_GUIDE.md` - 업데이트 완료

---

## 📋 검증 방법

### 1. Swagger UI에서 확인
```bash
# 1. 로컬 서버 실행
cd pet_project_backend
python run.py

# 2. 브라우저에서 Swagger UI 접속
# http://localhost:5000/swagger 또는 editor.swagger.io에 업로드

# 3. "Try it out" 버튼 클릭하여 실제 요청 URL 확인
```

**예상 결과:**
```
Request URL: http://localhost:5000/api/auth/google/authorize ✅
```

### 2. Postman에서 확인
```
1. Postman에서 OpenAPI 스펙 재 Import
2. "HappyDog - Development" 환경 선택
3. GET /api/auth/google/authorize 요청 실행
4. Console에서 실제 URL 확인
```

**예상 결과:**
```
GET http://localhost:5000/api/auth/google/authorize ✅
```

### 3. 스펙 파일 직접 확인
```bash
# servers 섹션 확인
grep -A 5 '"servers"' openapi_pretty.json
```

**예상 출력:**
```json
"servers": [
  {
    "url": "http://localhost:5000",      ✅
    "description": "Development"
  }
]
```

---

## 🎯 테스트 체크리스트

- [x] swagger_build.py 수정
- [x] OpenAPI 스펙 재생성
- [x] Postman 환경 변수 업데이트
- [x] 문서 업데이트
- [ ] Swagger UI에서 실제 테스트
- [ ] Postman에서 실제 테스트
- [ ] 프론트엔드 팀에 변경사항 공유

---

## 📝 참고사항

### OpenAPI 3.0 URL 조합 규칙
```
최종 URL = servers.url + paths.<path>

예시:
- servers.url: "http://api.example.com"
- path: "/users/123"
- 결과: "http://api.example.com/users/123"
```

### 왜 paths에 `/api`를 유지하는가?

**옵션 1: servers에 `/api` 포함** (이전 방식 - 잘못됨)
```json
"servers": [{"url": "http://localhost:5000/api"}],
"paths": {"/auth/login": {}}
→ http://localhost:5000/api/auth/login
```
❌ 문제: paths가 상대 경로로 표시되어 실제 API 구조가 불명확

**옵션 2: paths에 `/api` 포함** (현재 방식 - 올바름)
```json
"servers": [{"url": "http://localhost:5000"}],
"paths": {"/api/auth/login": {}}
→ http://localhost:5000/api/auth/login
```
✅ 장점: 
- paths에서 전체 API 경로 구조가 명확히 보임
- 서버만 변경하면 dev/prod 전환 가능
- Flask 라우트와 일치하는 경로 표시

---

## 🚀 향후 개선사항

### 1. CI/CD 파이프라인 추가
```yaml
# .github/workflows/openapi-validate.yml
- name: Validate OpenAPI Spec
  run: |
    python swagger_build.py --validate
    # /api/api 중복 검사
    ! grep -q '"url".*"/api"' openapi.json
```

### 2. 자동화된 URL 검증
```python
# swagger_build.py에 추가
def validate_no_duplicate_api_prefix(spec):
    for server in spec.get('servers', []):
        url = server.get('url', '')
        if url.endswith('/api'):
            raise ValueError(f"Server URL should not end with /api: {url}")
```

### 3. 문서화 개선
- API 설계 가이드에 URL 구조 규칙 추가
- 새 엔드포인트 추가 시 체크리스트 작성

---

## 📞 연락처

문제 발생 시:
- **Backend 팀**: swagger_build.py 수정 사항 확인
- **DevOps 팀**: 배포된 스펙 파일 버전 확인
- **Frontend 팀**: API 클라이언트 코드 재생성 필요 여부 확인

---

**최종 업데이트**: 2025-10-11  
**작성자**: AI Assistant  
**리뷰 필요**: Backend Lead
