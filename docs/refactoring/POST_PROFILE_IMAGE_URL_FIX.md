# Post Profile Image URL Fix

**날짜**: 2025-10-15  
**작성자**: GitHub Copilot  
**이슈**: Post의 `pet.profile_image_url`이 상대 경로로 저장되어 표시되지 않는 문제

---

## 🐛 문제 상황

### 현상
- 게시글(Post)의 `pet.profile_image_url`이 상대 경로(`pet_profiles/...`)로 저장됨
- 반면 게시글의 `image_urls`는 정상적으로 전체 Firebase Storage URL로 저장됨
- 프론트엔드에서 펫 프로필 이미지가 표시되지 않음

### 원인 분석
```python
# PostService.create_post() 기존 코드 (문제)
pet_info = PetInfo(
    pet_id=pet_data.get("pet_id"),
    name=pet_data.get("name"),
    breed=pet_data.get("breed"),
    birthdate=pet_data.get("birthdate"),
    profile_image_url=pet_data.get("profile_image_url")  # ← 상대 경로 그대로 사용
)

# 게시글 이미지는 변환됨
image_urls = self._convert_paths_to_urls(file_paths)  # ← URL로 변환
```

**핵심 문제**:
- `image_urls`는 `_convert_paths_to_urls()`로 Firebase Storage URL로 변환
- `profile_image_url`은 변환 없이 Firestore에서 가져온 값을 그대로 사용
- Pets 컬렉션에 상대 경로로 저장된 레거시 데이터가 있을 경우 문제 발생

---

## ✅ 해결 방안

### 1. 새로운 헬퍼 메서드 추가: `_convert_profile_image_url()`

펫 프로필 이미지 URL 변환을 위한 전용 메서드:

```python
def _convert_profile_image_url(self, profile_image_url: Optional[str]) -> Optional[str]:
    """
    펫 프로필 이미지 URL을 상대 경로에서 전체 URL로 변환합니다.
    
    Note:
        - 이미 전체 URL(https://로 시작)이면 그대로 반환
        - 상대 경로이면 Firebase Storage URL로 변환
        - None이거나 빈 문자열이면 None 반환
        - 변환 실패 시 경고 로그 출력 후 원본 반환 (에러 발생 안 함)
    
    Args:
        profile_image_url: 펫 프로필 이미지 경로 또는 URL
        
    Returns:
        Firebase Storage URL 또는 None
    """
    if not profile_image_url:
        return None
    
    # 이미 전체 URL인 경우
    if profile_image_url.startswith('https://'):
        return profile_image_url
    
    # StorageService가 없으면 원본 반환
    if not self.storage_service:
        logging.warning(f"StorageService가 없어 profile_image_url 변환 불가: {profile_image_url}")
        return profile_image_url
    
    # 상대 경로를 URL로 변환
    try:
        return self.storage_service.get_public_url(profile_image_url)
    except Exception as e:
        logging.warning(f"Profile image URL 변환 실패 (fallback to original): {profile_image_url} - {e}")
        return profile_image_url
```

**특징**:
- 비파괴적(Non-throwing): 변환 실패 시 원본 반환
- 유연성: 상대 경로/전체 URL/None 모두 처리 가능
- 명확한 책임: 펫 프로필 이미지 URL 변환만 담당

---

### 2. `create_post()` 수정: 펫 정보 스냅샷 시 URL 변환

```python
# Before
pet_info = PetInfo(
    pet_id=pet_data.get("pet_id"),
    name=pet_data.get("name"),
    breed=pet_data.get("breed"),
    birthdate=pet_data.get("birthdate"),
    profile_image_url=pet_data.get("profile_image_url")  # ← 상대 경로 그대로
)

# After
# profile_image_url을 상대 경로에서 전체 URL로 변환
profile_image_url = self._convert_profile_image_url(pet_data.get("profile_image_url"))

pet_info = PetInfo(
    pet_id=pet_data.get("pet_id"),
    name=pet_data.get("name"),
    breed=pet_data.get("breed"),
    birthdate=pet_data.get("birthdate"),
    profile_image_url=profile_image_url  # ← 전체 URL 사용
)
```

---

### 3. `_ensure_full_image_urls()` 확장: 기존 데이터 호환성

조회 시에도 레거시 데이터를 처리하도록 확장:

```python
def _ensure_full_image_urls(self, post_data: Dict[str, Any]) -> None:
    """
    image_urls와 pet.profile_image_url이 상대 경로인 경우 전체 URL로 변환합니다.
    기존 데이터 호환성을 위한 헬퍼 메서드입니다.
    """
    if not post_data or not self.storage_service:
        return
    
    # 1. image_urls 변환 (기존 로직 유지)
    if 'image_urls' in post_data and post_data['image_urls']:
        image_urls = post_data['image_urls']
        converted_urls = []
        for url in image_urls:
            if url and not url.startswith('https://'):
                try:
                    full_url = self.storage_service.get_public_url(url)
                    converted_urls.append(full_url)
                except Exception as e:
                    logging.warning(f"URL 변환 실패 (fallback to original): {url} - {e}")
                    converted_urls.append(url)
            else:
                converted_urls.append(url)
        post_data['image_urls'] = converted_urls
    
    # 2. pet.profile_image_url 변환 (새로 추가)
    if 'pet' in post_data and isinstance(post_data['pet'], dict):
        pet_data = post_data['pet']
        if 'profile_image_url' in pet_data:
            profile_url = pet_data.get('profile_image_url')
            if profile_url and not profile_url.startswith('https://'):
                try:
                    full_url = self.storage_service.get_public_url(profile_url)
                    pet_data['profile_image_url'] = full_url
                except Exception as e:
                    logging.warning(f"Profile image URL 변환 실패 (fallback to original): {profile_url} - {e}")
```

**호출되는 곳**:
- `get_posts()`: 피드 목록 조회 시
- `get_post_by_id()`: 개별 게시글 조회 시
- `get_posts_by_user()`: 사용자별 게시글 조회 시

---

## 📋 영향 범위

### 수정된 파일
- `pet_project_backend/app/api/posts/services/post_service.py`
  - 새로운 메서드: `_convert_profile_image_url()`
  - 수정된 메서드: `create_post()`, `_ensure_full_image_urls()`

### 수정된 문서
- `docs/refactoring/IMAGE_URL_REFACTORING.md`
  - PostService 섹션에 `_convert_profile_image_url()` 설명 추가
  - `_ensure_full_image_urls()` 확장 내역 추가

---

## 🔍 데이터 마이그레이션 불필요

### 이유
1. **새로운 게시글**: `create_post()`에서 자동으로 전체 URL 저장
2. **기존 게시글**: `_ensure_full_image_urls()`가 조회 시 자동 변환
3. **레거시 데이터**: Firestore에 상대 경로로 남아 있어도 API 응답에서는 전체 URL로 반환

### 검증 방법
```bash
# 1. 새로운 게시글 생성 테스트
POST /api/posts
{
  "text": "테스트 게시글",
  "file_paths": ["posts/user123/abc.jpg"]
}

# 2. 응답 확인
{
  "pet": {
    "profile_image_url": "https://firebasestorage.googleapis.com/..."  # ← 전체 URL
  },
  "image_urls": ["https://firebasestorage.googleapis.com/..."]  # ← 전체 URL
}

# 3. 기존 게시글 조회 테스트
GET /api/posts/{post_id}

# 4. 응답 확인 (레거시 데이터도 자동 변환됨)
{
  "pet": {
    "profile_image_url": "https://firebasestorage.googleapis.com/..."  # ← 자동 변환
  }
}
```

---

## 🎯 SOLID 원칙 준수

### Single Responsibility Principle (SRP)
- `_convert_profile_image_url()`: 펫 프로필 이미지 URL 변환만 담당
- `_convert_paths_to_urls()`: 게시글 이미지 URL 변환만 담당
- 각 메서드가 명확한 단일 책임을 가짐

### Open-Closed Principle (OCP)
- 기존 `_convert_paths_to_urls()` 로직 수정 없이 새로운 메서드 추가
- `_ensure_full_image_urls()`에 새로운 변환 로직 추가 (기존 로직 유지)

### Dependency Inversion Principle (DIP)
- `StorageService` 인터페이스에 의존 (구현 세부사항 분리)
- `storage_service.get_public_url()` 추상화 사용

---

## 🔧 향후 개선 사항

### 1. Firestore 데이터 정규화 (선택적)
현재는 조회 시 변환하지만, 필요하다면 배치 작업으로 Firestore 데이터를 정규화할 수 있습니다:

```python
# scripts/migrate_post_profile_image_urls.py
"""
Posts 컬렉션의 pet.profile_image_url을 상대 경로에서 전체 URL로 마이그레이션
"""
def migrate_post_profile_image_urls(storage_service, db_client):
    posts_ref = db_client.collection('posts')
    
    for doc in posts_ref.stream():
        post_data = doc.to_dict()
        if 'pet' in post_data and 'profile_image_url' in post_data['pet']:
            profile_url = post_data['pet']['profile_image_url']
            
            # 상대 경로인 경우에만 변환
            if profile_url and not profile_url.startswith('https://'):
                try:
                    full_url = storage_service.get_public_url(profile_url)
                    posts_ref.document(doc.id).update({
                        'pet.profile_image_url': full_url
                    })
                    print(f"✅ Updated post {doc.id}")
                except Exception as e:
                    print(f"❌ Failed to update post {doc.id}: {e}")
```

**실행 여부**:
- 현재는 불필요 (조회 시 자동 변환)
- 대량의 게시글이 있고 성능 최적화가 필요할 경우 고려

---

## 📚 관련 문서
- [IMAGE_URL_REFACTORING.md](./IMAGE_URL_REFACTORING.md): 이미지 URL 생성 리팩토링 전체 문서
- [API_DOCSTYLE.md](../API_DOCSTYLE.md): API 문서화 규칙
- [.github/copilot-instructions.md](../../.github/copilot-instructions.md): 프로젝트 전체 규칙

---

## ✅ 체크리스트

- [x] `PostService._convert_profile_image_url()` 메서드 추가
- [x] `PostService.create_post()`에서 `profile_image_url` 변환 적용
- [x] `PostService._ensure_full_image_urls()`에 `pet.profile_image_url` 변환 추가
- [x] 문서 업데이트 (`IMAGE_URL_REFACTORING.md`)
- [x] 에러 체크 (No errors found)
- [ ] 통합 테스트 (수동 검증 필요)
- [ ] 배포 후 프론트엔드에서 펫 프로필 이미지 표시 확인

---

## 🚀 배포 후 검증

1. **새로운 게시글 작성**
   - 펫 프로필 이미지가 있는 사용자로 게시글 작성
   - 응답의 `pet.profile_image_url`이 전체 URL인지 확인

2. **기존 게시글 조회**
   - 피드 목록 조회 (`GET /api/posts`)
   - 각 게시글의 `pet.profile_image_url`이 전체 URL인지 확인

3. **프론트엔드 확인**
   - 게시글 피드에서 펫 프로필 이미지가 정상 표시되는지 확인
   - 이미지 로딩 실패 시 네트워크 탭에서 URL 확인

---

**완료 시각**: 2025-10-15  
**테스트 상태**: 코드 수정 완료, 통합 테스트 대기중
