# Posts 도메인: 이미지 선택적 게시글 작성 기능 패치

**작성일**: 2025-10-10  
**대상 도메인**: Posts (게시글)  
**변경 유형**: 기능 개선 (Breaking Change 없음)

---

## 📋 변경 요약

게시글 작성 시 **이미지를 필수에서 선택적(optional)으로 변경**하여, 텍스트만으로도 게시글을 작성할 수 있도록 개선했습니다.

### 변경 전
- 게시글 작성 시 `text` (필수) + `file_paths` (필수, 최소 1개)
- 이미지 없이는 게시글 작성 불가

### 변경 후
- 게시글 작성 시 `text` (필수) + `file_paths` (선택적, 없어도 됨)
- 텍스트만으로 게시글 작성 가능
- 이미지가 없으면 `image_urls`는 빈 리스트(`[]`)로 저장 및 반환

---

## 🔧 변경된 파일

### 1. `pet_project_backend/app/api/posts/schemas.py`

#### 변경 내용
- **PostCreateSchema**: `file_paths` 필드를 선택적으로 변경
  - `required=True` → `required=False`
  - `validate=validate.Length(min=1)` → `validate=validate.Length(min=0)`
  - `missing=[]` 추가: 필드가 없을 때 빈 리스트로 기본값 설정

- **PostResponseSchema**: `image_urls` 필드에 `allow_none=True` 추가
  - 이미지가 없는 게시글도 정상적으로 직렬화되도록 보장

#### 변경 코드
```python
# PostCreateSchema
file_paths = fields.List(fields.Str(), required=False, load_default=[], validate=validate.Length(min=0))

# PostResponseSchema
image_urls = fields.List(fields.URL(), required=True, allow_none=True)
```

> **참고**: Marshmallow 3.x에서는 `missing` 대신 `load_default`를 사용합니다.

---

### 2. `pet_project_backend/app/api/posts/services/post_service.py`

#### 변경 내용
- **create_post 메서드 시그니처 변경**
  - `file_paths: List[str]` → `file_paths: Optional[List[str]] = None`
  - `file_paths`가 `None`이거나 빈 리스트일 때 빈 리스트로 처리: `file_paths or []`

- **Docstring 업데이트**
  - `file_paths`가 선택적임을 명시
  - 이미지 없이 텍스트만으로 게시글 작성 가능함을 문서화

#### 변경 코드
```python
def create_post(self, user_id: str, text: str, file_paths: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """새로운 게시글을 생성하고 Firestore에 저장합니다.
    
    Args:
        user_id: 작성자 사용자 ID
        text: 게시글 텍스트
        file_paths: Storage에 업로드된 파일의 상대 경로 리스트 (선택적, 없으면 텍스트만 게시글)
    
    Returns:
        생성된 게시글 정보 (image_urls는 Firebase Storage URL 포함, 이미지 없으면 빈 리스트)
    
    Note:
        file_paths가 None이거나 빈 리스트면 텍스트만으로 게시글이 생성됩니다.
    """
    # file_paths를 Firebase Storage URL로 변환 (None이면 빈 리스트로 처리)
    image_urls = self._convert_paths_to_urls(file_paths or [])
    # ... (이하 동일)
```

#### 참고사항
- `_convert_paths_to_urls` 메서드는 이미 빈 리스트를 받으면 빈 리스트를 반환하도록 구현되어 있어 추가 수정 불필요
- Storage Service가 없는 경우(예: DOCS_MODE)에도 정상 동작 보장

---

### 3. `pet_project_backend/app/api/posts/routes.py`

#### 변경 내용
- **create_post 엔드포인트 docstring 업데이트**
  - 이미지가 선택적임을 명시
  - 텍스트만으로 게시글 작성 가능함을 문서화

#### 변경 코드
```python
def create_post():
    """게시글을 생성합니다.

    클라이언트는 필수로 텍스트(`text`)를 전달하고, 선택적으로 업로드 완료된 파일 경로 리스트(`file_paths`)를 전달할 수 있습니다.
    이미지 없이 텍스트만으로도 게시글 작성이 가능합니다.
    성공 시 생성된 게시글의 전체 정보를 201 응답으로 반환하며, 생성 이벤트 후속 처리(post_events_service)가 비동기/후속 로직을 트리거합니다.

    RequestSchema: PostCreateSchema
    ResponseSchema[201]: PostResponseSchema
    """
```

#### 참고사항
- 로직 자체는 수정 불필요: Marshmallow 스키마가 `load_default=[]`로 설정되어 있어 `file_paths`가 없으면 자동으로 빈 리스트로 채워짐
- 기존 검증 로직 그대로 사용 가능

---

## 📝 비즈니스 로직 검증

### ✅ 유지되는 규칙
1. **텍스트는 여전히 필수**: `text` 필드는 `required=True` 유지
   - 빈 게시글(텍스트도 이미지도 없음) 작성 불가
   - 최소 1자 이상의 텍스트 필요 (`validate.Length(min=1, max=2000)`)

2. **이미지는 선택적**: `file_paths` 필드는 `required=False`
   - 제공되지 않으면 빈 리스트로 처리
   - 제공되면 기존과 동일하게 처리 (Firebase Storage URL 변환)

### ✅ 예상 시나리오

#### 시나리오 1: 텍스트만 있는 게시글
```json
// Request
{
  "text": "오늘 날씨가 정말 좋네요!"
}

// Response
{
  "post_id": "abc123",
  "text": "오늘 날씨가 정말 좋네요!",
  "image_urls": [],
  "author": { ... },
  "pet": { ... },
  ...
}
```

#### 시나리오 2: 텍스트 + 이미지 (기존과 동일)
```json
// Request
{
  "text": "우리 강아지 산책 사진이에요!",
  "file_paths": ["posts/user123/image1.jpg"]
}

// Response
{
  "post_id": "def456",
  "text": "우리 강아지 산책 사진이에요!",
  "image_urls": ["https://storage.googleapis.com/.../image1.jpg"],
  ...
}
```

#### 시나리오 3: 텍스트 없음 (실패)
```json
// Request
{
  "file_paths": ["posts/user123/image1.jpg"]
}

// Response (400 Bad Request)
{
  "error_code": "VALIDATION_ERROR",
  "message": "...",
  "details": {
    "text": ["Missing data for required field."]
  }
}
```

---

## 🔄 API 변경사항 (OpenAPI)

### POST `/api/posts`

#### Request Body (변경)
- `text`: **required** (string, 1-2000자)
- `file_paths`: **optional** (array of strings, 기본값: `[]`)

#### Response (변경 없음)
- `image_urls`: array (빈 리스트 가능)
- 기존 필드 모두 유지

#### Swagger 문서 재생성
- `openapi.json` 및 `openapi_pretty.json` 업데이트 완료
- Task: "Rebuild Swagger (docs mode)" 실행 완료

---

## 📊 영향 범위

### ✅ 영향받는 부분
1. **클라이언트 앱 (iOS/Android)**
   - 게시글 작성 UI: 이미지 첨부를 선택적으로 변경 가능
   - API 호출 시 `file_paths` 필드를 생략해도 됨

2. **백엔드 검증 로직**
   - Marshmallow 스키마가 자동으로 처리
   - 서비스 레이어는 빈 리스트를 정상 처리

### ❌ 영향받지 않는 부분
1. **기존 게시글 데이터**
   - DB 스키마 변경 없음
   - 기존 게시글은 모두 `image_urls` 필드가 있음 (빈 리스트 또는 URL 배열)

2. **다른 API 엔드포인트**
   - GET, PATCH, DELETE 엔드포인트는 변경 없음
   - 이미지 조회/표시 로직 변경 없음

3. **알림 및 이벤트 처리**
   - `post_events_service.handle_post_created()`는 이미지 유무와 무관하게 동작
   - 기존 로직 그대로 사용 가능

---

## 🧪 테스트 권장사항

### 단위 테스트
1. **스키마 검증 테스트**
   - `file_paths` 필드가 없는 요청 검증 성공 확인
   - `file_paths`가 빈 리스트일 때 처리 확인
   - `text` 필드가 없는 요청 검증 실패 확인

2. **서비스 레이어 테스트**
   - `create_post(user_id, text, file_paths=None)` 호출 시 빈 `image_urls` 반환 확인
   - `create_post(user_id, text, file_paths=[])` 호출 시 빈 `image_urls` 반환 확인
   - 이미지가 있는 경우 기존과 동일하게 동작하는지 확인

### 통합 테스트
1. **API 엔드포인트 테스트**
   - POST `/api/posts` 호출 시 `file_paths` 없이 게시글 생성 성공 확인
   - 생성된 게시글의 `image_urls`가 빈 리스트인지 확인
   - 이미지가 있는 게시글도 정상 작성되는지 확인

2. **UI 연동 테스트**
   - 텍스트만 입력하고 이미지 없이 게시글 작성 성공 확인
   - 피드에서 이미지 없는 게시글이 정상 표시되는지 확인

---

## 🚀 배포 체크리스트

- [x] 스키마 변경 완료 (`schemas.py`)
- [x] Marshmallow 3.x 호환성 수정 (`missing` → `load_default`)
- [x] 서비스 로직 변경 완료 (`post_service.py`)
- [x] 라우트 docstring 업데이트 완료 (`routes.py`)
- [x] OpenAPI 문서 재생성 완료 (`openapi.json`, `openapi_pretty.json`)
- [x] 변경사항 문서화 완료 (본 문서)
- [ ] 단위 테스트 작성 및 실행 (권장)
- [ ] 통합 테스트 실행 (권장)
- [ ] 클라이언트 팀에 API 변경사항 전달
- [ ] 배포 후 모니터링 (이미지 없는 게시글 생성 로그 확인)

---

## 📚 참고 문서

- **API Docstyle 가이드**: `docs/API_DOCSTYLE.md`
- **프로젝트 지침**: `.github/copilot-instructions.md`
- **OpenAPI 스펙**: `openapi_pretty.json` (POST `/api/posts` 참조)

---

## 💡 추가 고려사항

### 향후 개선 가능 사항
1. **최대 이미지 개수 제한**
   - 현재는 제한 없음 (빈 리스트 ~ 무제한)
   - 필요시 `validate.Length(max=10)` 등 추가 가능

2. **텍스트 길이 최적화**
   - 현재 최대 2000자
   - 사용 패턴에 따라 조정 가능

3. **이미지 크기/형식 검증**
   - 현재는 Storage 업로드 단계에서 검증
   - 추가 검증이 필요하면 별도 로직 추가 가능

### 하위 호환성
- **Breaking Change 없음**: 기존 클라이언트는 여전히 `file_paths`를 전달할 수 있음
- **점진적 적용 가능**: 클라이언트 앱을 업데이트하지 않아도 기존 기능 정상 동작

---

**작성자**: GitHub Copilot  
**검토 필요**: Backend Team Lead
