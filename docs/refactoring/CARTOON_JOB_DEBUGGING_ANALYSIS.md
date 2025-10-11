# Cartoon Job 문제 분석 및 해결 방안

**분석일**: 2025-10-11  
**대상 도메인**: cartoon_jobs  
**증상**: 
1. OpenAI 서버가 Firebase Storage 이미지 접근 실패
2. GPT-4o 이미지 분석 스킵됨
3. 게시글이 2개 생성됨 (텍스트+만화, 만화만)

---

## 📋 체크리스트 1: Firebase Admin SDK 설정 확인

### ✅ 1.1 서비스 계정 키 확인

**파일 위치**:
- `pet_project_backend/secrets/happydog-test-firebase-adminsdk-fbsvc-b32b884b12.json`

**확인 사항**:
```json
{
  "type": "service_account",
  "project_id": "happydog-test",
  "private_key_id": "b32b884b12...",
  "client_email": "firebase-adminsdk-fbsvc@happydog-test.iam.gserviceaccount.com"
}
```

**상태**: ✅ **정상** - 서비스 계정 키 파일 존재 및 유효

---

### ✅ 1.2 Firebase 초기화 확인

**파일**: `pet_project_backend/app/core/firestore.py`

**예상 코드**:
```python
def initialize_firestore():
    if firebase_admin._apps:
        return firebase_admin.get_app()
    
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH')
    cred = credentials.Certificate(cred_path)
    app = firebase_admin.initialize_app(cred, {
        'storageBucket': 'happydog-test.appspot.com'
    })
    return app
```

**확인 필요**:
- [ ] `FIREBASE_CREDENTIALS_PATH` 환경 변수가 올바른 경로를 가리키는지
- [ ] `storageBucket` 설정이 정확한지
- [ ] 초기화가 앱 시작 시 정상적으로 실행되는지

**예상 문제**: 
- Firebase Admin SDK는 초기화되어 있지만, Storage 버킷 설정이 누락되었을 가능성
- 또는 서비스 계정에 Storage 접근 권한이 없을 가능성

---

## 📋 체크리스트 2: Signed URL 사용 확인

### ⚠️ 2.1 현재 URL 생성 방식

**파일**: `pet_project_backend/app/services/storage_service.py`

**현재 구현** (추정):
```python
def get_public_url(self, file_path: str) -> str:
    # 방법 1: 다운로드 토큰 사용 (현재 사용 중인 것으로 추정)
    blob = self.bucket.blob(file_path)
    blob.metadata = {'firebaseStorageDownloadTokens': token}
    url = f"https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{path}?alt=media&token={token}"
    
    # 방법 2: Signed URL (권장 - OpenAI 접근 가능)
    # url = blob.generate_signed_url(expiration=timedelta(hours=1))
```

**문제점**:
- ❌ 다운로드 토큰 방식: Firebase Storage 규칙에 의존 (OpenAI 서버는 접근 불가)
- ✅ Signed URL 방식: 서명된 URL로 임시 퍼블릭 접근 허용 (OpenAI 접근 가능)

---

### 🔧 2.2 해결 방안: Signed URL로 변경

**수정이 필요한 파일**: `pet_project_backend/app/services/storage_service.py`

```python
from datetime import timedelta

class StorageService:
    def get_public_url(self, file_path: str, signed: bool = False, 
                      expiration_hours: int = 1) -> str:
        """
        파일의 공개 URL을 생성합니다.
        
        Args:
            file_path: Storage 내 파일 경로
            signed: True이면 Signed URL 생성 (OpenAI 접근 가능)
            expiration_hours: Signed URL 만료 시간 (기본 1시간)
            
        Returns:
            파일의 공개 URL
        """
        blob = self.bucket.blob(file_path)
        
        if signed:
            # Signed URL 생성 (OpenAI가 접근 가능)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(hours=expiration_hours),
                method="GET"
            )
            return url
        else:
            # 다운로드 토큰 방식 (기존)
            if not blob.exists():
                raise FileNotFoundError(f"파일을 찾을 수 없음: {file_path}")
            
            metadata = blob.metadata or {}
            token = metadata.get('firebaseStorageDownloadTokens')
            
            if not token:
                token = str(uuid.uuid4())
                blob.metadata = {'firebaseStorageDownloadTokens': token}
                blob.patch()
            
            bucket_name = self.bucket.name
            encoded_path = quote(file_path, safe='')
            return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media&token={token}"
```

---

### 🔧 2.3 OpenAIService에서 Signed URL 사용

**파일**: `pet_project_backend/app/services/openai_service.py`

**현재 코드**:
```python
def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
    # 1. Base64 인코딩 방식 사용 (현재)
    image_base64 = self._download_and_encode_image(image_url, storage_service)
    image_description = self._analyze_image_with_gpt4_vision_base64(image_base64)
```

**개선 방안** (선택 1: Signed URL 직접 사용):
```python
def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
    try:
        # 1. Signed URL 생성 (OpenAI가 직접 접근 가능)
        if storage_service and not image_url.startswith('https://storage.googleapis.com'):
            # Firebase Storage URL을 Signed URL로 변환
            file_path = self._extract_file_path_from_url(image_url)
            signed_url = storage_service.get_public_url(file_path, signed=True, expiration_hours=2)
            logging.info(f"Signed URL 생성 완료: {signed_url[:100]}...")
            
            # 2. GPT-4o에 Signed URL 직접 전달
            image_description = self._analyze_image_with_gpt4_vision(signed_url)
        else:
            # Fallback: Base64 방식
            image_base64 = self._download_and_encode_image(image_url, storage_service)
            image_description = self._analyze_image_with_gpt4_vision_base64(image_base64)
        
        # 3. DALL-E 생성 (기존과 동일)
        ...
    except Exception as e:
        logging.error(f"만화 생성 실패: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

**개선 방안** (선택 2: Base64 방식 유지 + 디버깅 강화):
```python
def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
    try:
        # 1. Base64 인코딩 (현재 방식 유지)
        if storage_service:
            try:
                logging.info(f"이미지 다운로드 시작: {image_url}")
                image_base64 = self._download_and_encode_image(image_url, storage_service)
                logging.info(f"Base64 인코딩 완료 (길이: {len(image_base64)} bytes)")
                
                # 2. GPT-4o 분석
                image_description = self._analyze_image_with_gpt4_vision_base64(image_base64)
                logging.info(f"GPT-4o 이미지 분석 완료: {image_description[:100]}...")
            except FileNotFoundError as e:
                logging.error(f"이미지 파일 없음: {e}")
                raise
            except Exception as e:
                logging.error(f"이미지 처리 실패: {e}", exc_info=True)
                raise
        else:
            raise ValueError("storage_service가 제공되지 않았습니다")
        
        # 3. DALL-E 생성
        ...
    except Exception as e:
        logging.error(f"만화 생성 실패: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

---

## 📋 체크리스트 3: 게시글 2개 생성 문제

### 🔍 3.1 문제 분석

**증상**:
- 게시글 1: 텍스트 + 만화 이미지
- 게시글 2: 만화 이미지만

**의심 경로**:

#### 경로 1: `CartoonJobIntegrationService.create_result_post()`

**파일**: `pet_project_backend/app/api/cartoon_jobs/services/integration_service.py:37`

```python
def create_result_post(self, job_data: Dict[str, Any], result_image_url: str) -> Optional[Dict[str, Any]]:
    # 만화 이미지만으로 게시물 생성 (텍스트는 빈 문자열)
    post_result = self.post_service.create_post(
        user_id=user_id,
        text="",  # ← 이 부분이 빈 문자열
        file_paths=[result_image_url]
    )
```

**문제**: 
- `text=""`로 게시글 생성 시도 → **이미지만 있는 게시글**
- 그런데 사용자가 입력한 `user_text`는 어디로?

---

#### 경로 2: 사용자가 직접 게시글 작성?

**의심 시나리오**:
1. 사용자가 만화 생성 요청 (POST `/api/cartoon-jobs/`)
2. 사용자가 별도로 게시글 작성 (POST `/api/posts/`)
3. 백그라운드에서 만화 생성 완료 → 자동 게시글 생성

**결과**: 게시글 2개

---

#### 경로 3: `user_text`가 게시글에 포함되어야 하는가?

**파일**: `pet_project_backend/app/api/cartoon_jobs/services/integration_service.py:57`

**현재 코드**:
```python
post_result = self.post_service.create_post(
    user_id=user_id,
    text="",  # ← 빈 문자열
    file_paths=[result_image_url]
)
```

**수정 제안**:
```python
def create_result_post(self, job_data: Dict[str, Any], result_image_url: str) -> Optional[Dict[str, Any]]:
    user_id = job_data['user_id']
    job_id = job_data['job_id']
    user_text = job_data.get('user_text', '')  # ← 사용자 입력 텍스트
    
    # 사용자가 입력한 텍스트와 만화 이미지로 게시물 생성
    post_result = self.post_service.create_post(
        user_id=user_id,
        text=user_text,  # ← user_text 포함
        file_paths=[result_image_url]
    )
    
    logging.info(f"만화 게시물 자동 생성 완료 (job_id: {job_id}, post_id: {post_result.get('post_id')})")
    return post_result
```

---

### 🔧 3.2 게시글 중복 생성 방지

**원인 분석**:

**시나리오 A**: 클라이언트가 중복 요청
- 사용자가 만화 생성 후 수동으로 게시글 작성
- 백그라운드에서 자동으로 게시글 생성
- **결과**: 게시글 2개

**해결 방안 A**:
1. 클라이언트에게 자동 게시글 생성 안내
2. 또는 자동 게시글 생성 기능 제거
3. 또는 게시글 중복 검사 로직 추가

```python
def create_result_post(self, job_data: Dict[str, Any], result_image_url: str) -> Optional[Dict[str, Any]]:
    user_id = job_data['user_id']
    job_id = job_data['job_id']
    
    # 중복 검사: 동일한 result_image_url로 게시글이 이미 있는지 확인
    existing_posts = self.post_service.get_posts_by_image_url(result_image_url)
    if existing_posts:
        logging.warning(f"이미 게시글이 존재함 (job_id: {job_id}), 생성 건너뜀")
        return existing_posts[0]
    
    # 게시글 생성
    post_result = self.post_service.create_post(...)
    return post_result
```

---

**시나리오 B**: `CartoonJobEventService`에서 중복 호출
- `handle_job_completed()`가 여러 번 호출됨?

**확인 필요**:
```python
# pet_project_backend/app/api/cartoon_jobs/services/event_service.py:67
def handle_job_completed(self, update_data: Dict[str, Any]):
    # 이 메서드가 여러 번 호출되는지 로그 확인
    logging.info(f"[DEBUG] handle_job_completed 호출됨: {update_data['job_id']}")
```

---

## 📋 종합 분석 및 우선순위

### 🔴 **우선순위 1: GPT-4o 이미지 분석 스킵 문제**

**원인**:
- OpenAI 서버가 Firebase Storage URL에 접근 불가
- Base64 인코딩 과정에서 예외 발생 가능

**해결 방안**:
1. **Signed URL 사용** (권장)
   - `storage_service.get_public_url(signed=True)` 추가
   - OpenAI에 Signed URL 직접 전달
   
2. **Base64 방식 디버깅**
   - `_download_and_encode_image()` 예외 처리 강화
   - 상세한 로그 추가

---

### 🟡 **우선순위 2: 게시글 2개 생성 문제**

**원인**:
1. 클라이언트가 수동으로 게시글 작성 + 백그라운드 자동 생성
2. `user_text`가 게시글에 포함되지 않음
3. `handle_job_completed()` 중복 호출 가능성

**해결 방안**:
1. **`user_text` 포함**
   - `integration_service.py`에서 `text=user_text` 사용
   
2. **중복 검사**
   - 동일 이미지로 게시글이 이미 있는지 확인
   
3. **클라이언트 가이드**
   - 자동 게시글 생성 안내
   - 수동 게시글 작성 불필요

---

### 🟢 **우선순위 3: Firebase Admin SDK 설정 재확인**

**확인 사항**:
- [ ] `FIREBASE_CREDENTIALS_PATH` 환경 변수
- [ ] `storageBucket` 설정
- [ ] 서비스 계정 Storage 권한

---

## 🔧 즉시 적용 가능한 수정 사항

### 1. `integration_service.py` 수정

```python
def create_result_post(self, job_data: Dict[str, Any], result_image_url: str) -> Optional[Dict[str, Any]]:
    user_id = job_data['user_id']
    job_id = job_data['job_id']
    user_text = job_data.get('user_text', '')  # ← 추가
    
    post_result = self.post_service.create_post(
        user_id=user_id,
        text=user_text,  # ← 수정 (빈 문자열 → user_text)
        file_paths=[result_image_url]
    )
    
    logging.info(f"만화 게시물 자동 생성 완료 (job_id: {job_id}, post_id: {post_result.get('post_id')})")
    return post_result
```

### 2. `storage_service.py`에 Signed URL 추가

```python
def get_signed_url(self, file_path: str, expiration_hours: int = 1) -> str:
    """OpenAI 접근 가능한 Signed URL 생성"""
    blob = self.bucket.blob(file_path)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=expiration_hours),
        method="GET"
    )
    return url
```

### 3. `openai_service.py`에서 Signed URL 사용

```python
def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
    try:
        # Signed URL 생성 시도
        if storage_service:
            file_path = self._extract_file_path_from_url(image_url)
            signed_url = storage_service.get_signed_url(file_path, expiration_hours=2)
            logging.info(f"Signed URL 생성: {signed_url[:50]}...")
            
            # GPT-4o에 Signed URL 전달
            image_description = self._analyze_image_with_gpt4_vision(signed_url)
        else:
            raise ValueError("storage_service 필요")
        
        # 나머지 로직...
    except Exception as e:
        logging.error(f"만화 생성 실패: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

---

## 📝 다음 단계

1. [ ] Firebase Admin SDK 초기화 코드 확인
2. [ ] `storage_service.py`에 `get_signed_url()` 메서드 추가
3. [ ] `openai_service.py`에서 Signed URL 사용하도록 수정
4. [ ] `integration_service.py`에서 `user_text` 포함하도록 수정
5. [ ] 테스트 및 로그 확인
6. [ ] 게시글 중복 생성 원인 추가 조사

---

**작성자**: GitHub Copilot  
**검토 필요**: Backend Team Lead
