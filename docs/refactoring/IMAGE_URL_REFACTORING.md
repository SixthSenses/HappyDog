# Image URL Generation Refactoring

## 📅 Date: 2025-10-08
## 🎯 Objective: URL 생성 방식 통일 및 타이밍 문제 해결

---

## 🔍 문제 진단

### 발견된 문제들

1. **Firebase Storage Security Rules 차단** (Critical)
   - 기존: `allow read, write: if false` → 모든 접근 차단
   - 결과: 프론트엔드에서 이미지 URL 접근 시 403 Forbidden 에러
   - 해결: Security Rules 수정 완료 (사용자 요청)

2. **URL 생성 방식 혼란** (Medium)
   - 3가지 다른 메서드 혼재: `get_public_url()`, `make_public_and_get_url()`, `get_gcs_url()`
   - `make_public_and_get_url()`: GCS Public URL 생성 (Security Rules 적용 → 403 에러)
   - `get_gcs_url()`: GCS 표준 URL (Security Rules 적용 → 403 에러)
   - `get_public_url()`: Firebase Storage URL + 토큰 (Security Rules 우회 가능) ✅

3. **Post 생성 시 URL 변환 타이밍 문제** (Medium)
   - `create_post()`에서 파일 경로를 URL로 변환 시도
   - 파일이 아직 업로드되지 않았을 경우 FileNotFoundError 발생 가능
   - 에러 시 상대 경로를 그대로 저장 → 프론트에서 사용 불가

4. **기존 데이터 호환성 문제** (Low)
   - DB에 상대 경로로 저장된 레거시 데이터 존재
   - `_ensure_full_image_urls()` 메서드로 조회 시 변환 시도

---

## ✅ 적용된 해결 방안

### 1. StorageService 정리 (SRP: Single Responsibility Principle)

#### 제거된 메서드
```python
# ❌ Removed: make_public_and_get_url()
# 이유: Security Rules와 충돌, GCS Public URL은 토큰 없이 접근 불가

# ❌ Removed: get_gcs_url()
# 이유: Security Rules 적용되어 403 에러 발생
```

#### 개선된 메서드
```python
# ✅ Improved: get_public_url()
def get_public_url(self, file_path: str) -> str:
    """
    Firebase Storage URL (토큰 포함) 반환
    - 파일 존재 여부 확인 (FileNotFoundError 발생)
    - 토큰 없을 시 자동 생성 및 메타데이터 업데이트
    - Fallback: Signed URL (7일 만료)
    """
```

**SOLID 원칙 준수:**
- **SRP**: 단일 URL 생성 방식만 제공
- **ISP**: 필요 없는 메서드 제거, 인터페이스 단순화

---

### 2. PostService 개선 (OCP: Open-Closed Principle)

#### 새로운 메서드: `_convert_paths_to_urls()`
```python
def _convert_paths_to_urls(self, file_paths: List[str]) -> List[str]:
    """
    파일 경로를 Firebase Storage URL로 변환
    
    특징:
    - 이미 URL인 경우 (https:// 시작) 변환 스킵 ← OCP 준수
    - 파일 존재하지 않으면 FileNotFoundError 발생 (명확한 에러 처리)
    - StorageService 없으면 경고 후 원본 반환
    """
```

#### 개선된 `create_post()` 메서드
```python
def create_post(self, user_id: str, text: str, file_paths: List[str]) -> Optional[Dict[str, Any]]:
    """
    Args:
        file_paths: Storage에 업로드된 파일의 상대 경로 OR 이미 생성된 URL
    
    Note:
        - 클라이언트가 pre-signed URL로 업로드 완료한 파일 경로 필요
        - 다른 서비스(CartoonJobIntegrationService)에서 URL 전달 시에도 호환
    """
    image_urls = self._convert_paths_to_urls(file_paths)  # ← 통합 변환 로직
```

#### 레거시 데이터 지원: `_ensure_full_image_urls()`
```python
def _ensure_full_image_urls(self, post_data: Dict[str, Any]) -> None:
    """
    기존 DB에 상대 경로로 저장된 데이터 변환
    - 새로운 데이터는 이미 URL로 저장됨
    - URL 변환 실패 시 원본 유지 (에러 발생 안 함)
    """
```

**SOLID 원칙 준수:**
- **OCP**: 이미 URL인 경우를 지원하도록 확장 (기존 코드 수정 최소화)
- **DRY**: 중복된 URL 변환 로직을 `_convert_paths_to_urls()`로 통합
- **Fail-Fast**: 파일 존재하지 않으면 즉시 에러 발생 (잘못된 데이터 저장 방지)

---

### 3. PetProfileService 개선

#### 개선된 `update_profile_image()` 메서드
```python
def update_profile_image(self, pet_id: str, user_id: str, file_path: str) -> str:
    """
    Before: make_public_and_get_url() 사용 (GCS Public URL)
    After:  get_public_url() 사용 (Firebase Storage URL + 토큰)
    
    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
    """
    public_url = self.storage_service.get_public_url(file_path)  # ← 변경
```

#### 레거시 데이터 지원: `_ensure_full_profile_image_url()`
```python
def _ensure_full_profile_image_url(self, pet_data: Dict[str, Any]) -> None:
    """
    DB에 상대 경로로 저장된 기존 데이터 변환
    - URL 변환 실패 시 원본 유지
    """
```

**SOLID 원칙 준수:**
- **LSP**: 동일한 인터페이스 유지 (반환 타입 변경 없음)
- **DIP**: StorageService 인터페이스에 의존 (구현 세부사항 분리)

---

### 4. PetBiometricService 개선

#### 개선된 눈 분석 이미지 URL 생성
```python
# Before: make_public_and_get_url()
# After:  get_public_url()
try:
    image_url = self.storage_service.get_public_url(file_path)
    logging.info(f"Image URL generated for pet {pet_id}")
except Exception as e:
    logging.error(f"Failed to get image URL for pet {pet_id}: {e}")
    image_url = None  # Non-critical, 실패 시 None 반환
```

---

### 5. uploads/routes.py 개선

#### `/finalize-cartoon` 엔드포인트
```python
@uploads_bp.route('/finalize-cartoon', methods=['POST'])
def finalize_cartoon_upload():
    """
    Before: 만화 이미지 공개 전환 (make_public_and_get_url)
    After:  만화 이미지 URL 생성 (get_public_url)
    """
    public_url = storage_service.get_public_url(data['file_path'])  # ← 변경
```

---

### 6. PostStorageService 정리

#### 개선된 `cleanup_post_files()` 메서드
```python
def cleanup_post_files(self, file_paths: List[str]) -> None:
    """
    Firebase Storage URL에서 파일 경로 추출 및 삭제
    
    개선 사항:
    - URL 디코딩 로직 개선 (urllib.parse.unquote 사용)
    - 명확한 에러 로깅
    - 인식할 수 없는 URL 형식 경고
    """
```

#### 제거된 메서드
```python
# ❌ Removed: process_post_uploads() - 구현되지 않은 빈 메서드
# ❌ Removed: validate_image_files() - 사용되지 않는 메서드
```

**SOLID 원칙 준수:**
- **SRP**: Storage 정리 기능만 담당
- **YAGNI**: 사용하지 않는 메서드 제거

---

## 🎯 적용된 SOLID 원칙 요약

| 원칙 | 적용 사례 |
|------|----------|
| **SRP** | StorageService는 URL 생성만, PostService는 게시글 CRUD만 담당 |
| **OCP** | `_convert_paths_to_urls()`에서 URL인 경우를 지원하도록 확장 (수정 최소화) |
| **LSP** | 모든 서비스에서 동일한 StorageService 인터페이스 사용 |
| **ISP** | 불필요한 메서드(`make_public_and_get_url`, `get_gcs_url`) 제거 |
| **DIP** | 서비스들이 StorageService 추상화에 의존 (구현 세부사항 분리) |

---

## 📊 Before/After 비교

### URL 생성 방식
| Before | After |
|--------|-------|
| `make_public_and_get_url()` | `get_public_url()` (통일) |
| `get_gcs_url()` | 제거 |
| GCS Public URL (403 에러) | Firebase Storage URL + 토큰 ✅ |

### Post 생성 흐름
| Before | After |
|--------|-------|
| file_paths → try URL 변환 → fallback 상대 경로 저장 ❌ | file_paths → URL 변환 (이미 URL이면 스킵) → FileNotFoundError 발생 ✅ |
| 에러 처리 불명확 | 명확한 에러 발생 (Fail-Fast) |

### 레거시 데이터 처리
| Before | After |
|--------|-------|
| 조회 시마다 변환 시도 (성능 오버헤드) | 조회 시마다 변환 시도 (유지) |
| 새 데이터도 상대 경로 저장 가능 ❌ | 새 데이터는 항상 URL로 저장 ✅ |

---

## 🧪 테스트 체크리스트

### 필수 테스트
- [ ] 게시글 생성 (새 이미지 업로드)
- [ ] 게시글 조회 (레거시 데이터 포함)
- [ ] 만화 작업 완료 후 게시글 자동 생성
- [ ] Pet 프로필 이미지 업데이트
- [ ] 눈 분석 이미지 URL 생성
- [ ] 게시글 삭제 시 Storage 정리

### 엣지 케이스
- [ ] StorageService 없는 경우 (DOCS_MODE)
- [ ] 파일이 존재하지 않는 경우 (FileNotFoundError)
- [ ] 이미 URL인 file_paths 전달 시 (CartoonJob)
- [ ] 상대 경로와 URL 혼재된 file_paths

---

## 📝 Migration 가이드 (기존 데이터)

### Option 1: 점진적 마이그레이션 (권장)
- 새로운 데이터는 자동으로 URL로 저장됨
- 기존 데이터는 조회 시 자동 변환 (성능 영향 최소)
- 필요 시 배치 스크립트로 일괄 변환

### Option 2: 배치 마이그레이션
```python
# TODO: 필요 시 작성
# - Firestore 전체 posts/pets 컬렉션 스캔
# - 상대 경로를 URL로 변환하여 업데이트
# - 변환 실패 케이스 로깅
```

---

## 🚀 배포 체크리스트

- [x] Storage Security Rules 업데이트 확인
- [x] 코드 에러 없음 확인 (`get_errors()`)
- [x] SOLID 원칙 준수 확인
- [ ] 통합 테스트 실행
- [ ] 프론트엔드 이미지 표시 확인
- [ ] 로그 모니터링 (URL 변환 실패 여부)

---

## 🔗 관련 문서
- [API_DOCSTYLE.md](../API_DOCSTYLE.md)
- [SOLID_DI_Summary.md](./SOLID_DI_Summary.md)
- [.github/copilot-instructions.md](../../.github/copilot-instructions.md)
