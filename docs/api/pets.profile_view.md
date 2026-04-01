# 뷰 기반 반려동물 프로필 조회 가이드

- Endpoint: `GET /api/pets/profile`
- 인증: 선택적(`Authorization: Bearer <token>`). 단, 타인 프로필 조회 시 인증 필요.
- 스키마: `ResponseSchema[200]: PetViewBasedResponseSchema`

## ⚡ 성능 최적화: 서버 사이드 조인

**중요**: 이 엔드포인트는 **클라이언트 사이드 조인을 방지**하기 위해 설계되었습니다.

### 문제 상황
프론트엔드에서 다음과 같이 여러 API를 호출하면 성능 저하 발생:
```javascript
// ❌ 나쁜 예: 클라이언트 사이드 조인 (3번의 네트워크 요청)
const pet = await fetch('/api/pets/{pet_id}');
const user = await fetch('/api/users/{user_id}');  
const posts = await fetch('/api/posts?user_id={user_id}');
const profile = {
  ...pet,
  age: calculateAge(pet.birthdate),
  post_count: posts.length
};
```

### 백엔드 솔루션
**단일 요청**으로 모든 데이터를 서버에서 조인하여 반환:
```javascript
// ✅ 좋은 예: 서버 사이드 조인 (1번의 네트워크 요청)
const profile = await fetch('/api/pets/profile?user_id={user_id}&view=social');
// 응답에 age_months, post_count 등 파생 데이터 포함
```

### 백엔드 구현 핵심

**1) 최적화된 데이터 조회** (`PetProfileService.get_user_pet_profile`)
```python
def get_user_pet_profile(self, user_id: str) -> Optional[Pet]:
    """User 문서에서 pet_id를 먼저 조회 (인덱스 활용)"""
    user_ref = self.db.collection('users').document(user_id)
    user_data = user_ref.get().to_dict()
    pet_id = user_data.get('pet_id')
    
    # 직접 pet 문서 조회 (collection scan 없음)
    pet_doc = self.pets_ref.document(pet_id).get()
    return Pet.from_dict(pet_doc.to_dict())
```

**2) 뷰별 Presenter 패턴** (`PetPresenter.build_view_response`)
```python
@classmethod
def build_view_response(cls, pet: Pet, view: str, 
                       user_stats_service, target_user_id) -> Dict:
    data = cls._base(pet)  # 공통 필드
    
    if view == "social":
        cls._add_identity(pet, data)  # 생년월일, 성별, 품종
        cls._maybe_age(pet, data)     # 나이(개월) 계산
        
        # UserStatsService로 게시물 수 집계 (Firestore count 쿼리)
        stats = user_stats_service.get_user_stats(target_user_id)
        data["post_count"] = stats.get("post_count", 0)
    
    return data
```

**3) 게시물 수 집계** (`UserStatsService._count_posts_by_user_id`)
```python
def _count_posts_by_user_id(self, author_id: str) -> int:
    """Firestore의 count() API로 효율적 집계"""
    query = self.posts_ref.where('author.user_id', '==', author_id)
    count_result = query.count().get()
    return count_result[0][0].value  # 문서 로드 없이 카운트만 반환
```

### 성능 이점
| 방식 | 네트워크 요청 | DB 쿼리 | 데이터 전송량 |
|------|--------------|---------|--------------|
| 클라이언트 조인 | 3~5회 | 3~5회 | 높음 (모든 게시물 데이터) |
| **서버 사이드** | **1회** | **2~3회** | **낮음 (count만)** |

- 네트워크 왕복 시간 **70% 감소** (3회→1회)
- 모바일 환경에서 특히 유리 (레이턴시 절감)
- Firestore `count()` API로 게시물 데이터 전송 없이 집계

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

## 전체 요청 흐름 (코드 레벨)

### Route → Service → Presenter 아키텍처

**`routes.py` - 엔드포인트 진입점**
```python
@pets_bp.route('/profile', methods=['GET'])
@jwt_required(optional=True)
def get_pet_profile_by_view():
    current_user_id = get_jwt_identity()
    target_user_id = request.args.get('user_id', current_user_id)
    view = request.args.get('view', 'mypage')
    
    # 1) 접근 권한 검증
    policy = PetAccessPolicy()
    policy.ensure_view_permission(current_user_id, target_user_id, view)
    
    # 2) Pet 데이터 조회 (최적화된 단일 쿼리)
    pet_service = current_app.services['pets']
    pet_profile = pet_service.get_user_pet_profile(target_user_id)
    
    # 3) 뷰별 응답 구성 (서버 사이드 조인)
    user_stats = current_app.services.get('user_stats')
    response_data = PetPresenter.build_view_response(
        pet_profile, view, 
        user_stats_service=user_stats, 
        target_user_id=target_user_id
    )
    
    return jsonify(PetViewBasedResponseSchema().dump(response_data)), 200
```

**최적화 포인트**:
- ✅ Users 컬렉션에서 `pet_id` 직접 조회 (인덱스 활용)
- ✅ Firestore `count()` API로 게시물 수 집계 (문서 로드 불필요)
- ✅ Presenter 패턴으로 뷰별 필드 분기 (코드 재사용)
- ✅ 단일 HTTP 응답으로 모든 데이터 제공

---

## 통합 팁
- 기본값: `view` 미지정 시 `mypage`
- 프론트 측 분기 추천
  - 마이페이지/펫케어 화면: `view=mypage|petcare` (항상 본인 토큰 포함)
  - 프로필 공개 화면(타인): `user_id=<상대>` + `view=social` (토큰 있음이 안전)
- 스키마 일관성
  - 날짜: `birthdate`는 ISO `YYYY-MM-DD`
  - 성별: `gender`는 enum(`FEMALE`/`MALE`)

---

## 프론트엔드 마이그레이션 가이드

### Before (느린 코드)
```javascript
// ❌ 여러 번의 API 호출 + 클라이언트 계산
async function loadProfile(userId) {
  const pet = await api.get(`/pets/${petId}`);
  const user = await api.get(`/users/${userId}`);
  const posts = await api.get(`/posts?user_id=${userId}`);
  
  return {
    ...pet,
    age: calculateAge(pet.birthdate),  // 클라이언트 계산
    post_count: posts.length           // 전체 게시물 로드
  };
}
```

### After (빠른 코드)
```javascript
// ✅ 단일 API 호출 - 서버가 모두 처리
async function loadProfile(userId) {
  return await api.get('/pets/profile', {
    params: { user_id: userId, view: 'social' }
  });
  // 응답에 age_months, post_count 이미 포함됨
}
```

### 성능 측정 예시
```
Before: 평균 1.2초 (3G 환경)
- /pets/{id}: 400ms
- /users/{id}: 350ms  
- /posts?user_id: 450ms

After: 평균 420ms (3G 환경)
- /pets/profile: 420ms (단일 요청)

개선율: 65% 속도 향상 ⚡
```