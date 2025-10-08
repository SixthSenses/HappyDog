# Cartoon Job Debugging Guide

## 🔍 문제 진단 체크리스트

만화 생성이 실패할 때 다음 순서로 확인하세요:

### 1. 로그 확인

```bash
# 터미널에서 실행 중인 Flask 앱 로그 확인
```

**주요 로그 키워드:**
- `이미지 다운로드 시도:` - 원본 URL 확인
- `파싱:` - 파일 경로 추출 성공 여부
- `Base64 인코딩 완료:` - 인코딩 성공 여부
- `GPT-4o 분석 재시도` - API 호출 실패 원인

---

### 2. URL 형식 확인

**올바른 형식:**
```
✅ https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}?alt=media&token={token}
✅ https://storage.googleapis.com/{bucket}/{path}
✅ cartoon_sources/user_id/file.jpg
```

**잘못된 형식:**
```
❌ http://... (HTTPS 필수)
❌ file:///... (로컬 경로)
❌ blob:http://... (Blob URL)
```

---

### 3. 에러 메시지별 해결 방법

#### Error: "파일을 찾을 수 없습니다"

**원인:**
- Firebase Storage에 파일이 실제로 없음
- 파일 경로 추출 실패
- Bucket 이름 불일치

**해결:**
1. Firebase Console에서 파일 존재 확인
2. 로그에서 "추출된 파일 경로" 확인
3. Bucket 이름이 환경 변수와 일치하는지 확인

```python
# 올바른 환경 변수 설정
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

---

#### Error: "Error while downloading ... invalid_image_url"

**원인:**
- OpenAI 서버가 URL에 접근할 수 없음
- Firebase Storage Security Rules 차단
- Base64 인코딩 실패 후 URL 직접 사용 시도

**해결:**
1. Base64 인코딩이 성공했는지 로그 확인
2. Security Rules 확인:
   ```javascript
   // Firebase Console > Storage > Rules
   allow read: if request.auth != null || request.query.get('token', '').size() > 0;
   ```
3. 클라이언트가 토큰 포함된 URL을 보내는지 확인

---

#### Error: "이미지 분석이 3회 모두 실패"

**원인:**
- Base64 인코딩 실패
- OpenAI API 호출 실패
- 네트워크 오류

**해결:**
1. 로그에서 "Base64 인코딩 완료" 확인
2. OpenAI API 키 유효성 확인
3. 네트워크 연결 확인

---

### 4. Firebase Storage 파일 경로 확인

**올바른 경로 구조:**
```
cartoon_sources/
  ├── {user_id_1}/
  │   ├── {uuid_1}.jpg
  │   └── {uuid_2}.png
  └── {user_id_2}/
      └── {uuid_3}.jpg

cartoon_results/  (자동 생성됨)
  ├── {timestamp}_{uuid_1}.png
  └── {timestamp}_{uuid_2}.png
```

**확인 방법:**
```bash
# Firebase CLI 설치 후
firebase storage:list gs://your-bucket/cartoon_sources/
```

---

### 5. 수동 테스트

**Postman/Curl로 테스트:**

```bash
# 1. 업로드 URL 발급
curl -X POST https://your-api.com/api/uploads/url \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "upload_type": "cartoon_source_image",
    "filename": "test.jpg",
    "content_type": "image/jpeg"
  }'

# 2. 파일 업로드 (발급받은 upload_url 사용)
curl -X PUT "UPLOAD_URL" \
  -H "Content-Type: image/jpeg" \
  --data-binary @test.jpg

# 3. 만화 작업 생성
curl -X POST https://your-api.com/api/cartoon-jobs/ \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "file_paths": ["cartoon_sources/USER_ID/FILE_NAME.jpg"],
    "user_text": "테스트"
  }'
```

---

## 🛠️ 일반적인 해결 방법

### 방법 1: 환경 변수 재확인

```bash
# .env 파일 확인
cat pet_project_backend/.env | grep FIREBASE
cat pet_project_backend/.env | grep OPENAI
```

**필수 환경 변수:**
- `FIREBASE_STORAGE_BUCKET`
- `FIREBASE_CREDENTIALS_PATH`
- `OPENAI_API_KEY`

---

### 방법 2: Firebase Storage 권한 확인

1. Firebase Console > Storage > Rules
2. 다음 규칙 추가:

```javascript
rules_version = '2';
service firebase.storage {
  match /b/{bucket}/o {
    // 토큰 기반 읽기 허용
    match /{allPaths=**} {
      allow read: if request.auth != null || 
                     request.query.get('token', '').size() > 0;
    }
    
    // 만화 원본 업로드 (인증된 사용자)
    match /cartoon_sources/{userId}/{fileName} {
      allow write: if request.auth != null && request.auth.uid == userId;
    }
    
    // 만화 결과 (백엔드만 쓰기)
    match /cartoon_results/{fileName} {
      allow read: if true;
      // 백엔드는 Admin SDK 사용하므로 rules 우회
    }
  }
}
```

---

### 방법 3: 서버 재시작

```bash
# Ctrl+C로 서버 종료 후
cd pet_project_backend
python run.py
```

---

### 방법 4: 로그 레벨 증가

```python
# run.py 또는 __init__.py 상단에 추가
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📊 정상 동작 시 로그 흐름

```
INFO: 이미지 다운로드 시도: https://storage.googleapis.com/...
INFO: GCS URL 파싱: bucket=..., path=cartoon_sources/user_id/file.jpg
INFO: 추출된 파일 경로: cartoon_sources/user_id/file.jpg
INFO: 이미지 Base64 인코딩 완료: 123456 bytes
INFO: 이미지를 Base64로 인코딩 완료
[GPT-4o 호출 - 10-20초 소요]
INFO: DALL-E 생성 시작
[DALL-E 호출 - 30-60초 소요]
INFO: DALL-E 결과 이미지 저장 완료: cartoon_results/20251008_143052_a1b2c3d4.png
INFO: 만화 생성 작업 완료: job_id
```

---

## 🚨 긴급 해결 (임시 조치)

Base64 인코딩이 계속 실패할 경우:

```python
# app/services/openai_service.py의 generate_cartoon()에서
# storage_service 파라미터를 None으로 강제 설정

# CartoonJobProcessor에서:
result = openai_service.generate_cartoon(image_url, user_text, storage_service=None)
```

**주의:** 이 경우 Firebase Storage URL이 OpenAI 서버에서 접근 가능해야 합니다.

---

## 📞 추가 지원

문제가 해결되지 않으면 다음 정보를 포함하여 이슈 제기:

1. **로그 전체** (민감 정보 제거)
2. **URL 형식** (예시)
3. **Firebase Storage 파일 존재 여부** (스크린샷)
4. **환경 변수 설정** (값은 마스킹)
5. **OpenAI API 키 유효성** (테스트 결과)
