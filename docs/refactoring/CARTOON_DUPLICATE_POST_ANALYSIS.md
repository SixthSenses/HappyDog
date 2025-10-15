# Cartoon Job 중복 게시물 생성 문제 분석

**날짜**: 2025-10-15  
**이슈**: 만화 생성 작업 완료 시 동일한 이미지로 2개의 게시물이 생성됨  
**증상**: Firebase Storage에는 하나의 이미지만 존재하나, 서로 다른 post_id를 가진 2개의 게시물 생성

---

## 🔍 로그 분석

### 관찰된 패턴
```
11:29:08 - POST /api/uploads/url (업로드 URL 발급)
11:29:09 - POST /api/cartoon-jobs/ (작업 생성, 202 Accepted)
11:29:09 - GET /api/cartoon-jobs/8df5... (polling 시작)
...
11:29:56 - GET /api/cartoon-jobs/8df5... (polling 계속, 약 24회)
11:29:59 - POST /api/posts/ (게시물 생성, 201 Created) ← 첫 번째 게시물
11:29:59 - GET /api/users/me
11:30:01 - GET /api/posts/?limit=20 (피드 조회) ← 두 번 호출됨
11:30:01 - GET /api/posts/?limit=20
```

### 핵심 관찰 사항
1. **백엔드에서 게시물 자동 생성**: `11:29:59 - POST /api/posts/` (프론트엔드 요청)
2. **중복된 피드 조회**: `11:30:01 - GET /api/posts/?limit=20` (두 번 호출)
3. **프론트엔드의 polling**: 약 2초마다 작업 상태 조회 (총 24회)
4. **게시물 생성 시점**: 작업 완료 직후

---

## 🐛 문제 원인 분석

### 1차 의심: 백엔드 중복 생성 (❌ 가능성 낮음)

#### 백엔드 흐름
```python
# processor_service.py (_process_job)
update_data = job_service.update_job_status(job_id, CartoonJobStatus.COMPLETED, result_data)
job_events.handle_job_completed(update_data)  # ← 한 번만 호출됨

# event_service.py (handle_job_completed)
post_result = job_integration.create_result_post(job, result_image_url)  # ← 한 번만 호출됨

# integration_service.py (create_result_post)
post_result = self.post_service.create_post(
    user_id=user_id,
    text=user_text,
    file_paths=[result_image_url]
)
```

**검증 포인트**:
- `_process_job()`는 ThreadPoolExecutor의 `submit()`으로 한 번만 실행됨
- 작업 완료는 `update_job_status()`로 Firestore에 기록되며, 이는 멱등성 보장
- 로그에 `POST /api/posts/`가 **한 번만** 나타남 ✅

**결론**: 백엔드에서 중복 생성 가능성은 매우 낮음

---

### 2차 의심: 프론트엔드 중복 요청 (✅ 가능성 높음)

#### 의심되는 시나리오

**시나리오 A: Polling 완료 후 수동 게시물 생성**
```
1. 프론트엔드가 2초마다 작업 상태 polling (GET /api/cartoon-jobs/{id})
2. 작업 완료 감지 (status: COMPLETED, result_image_url 포함)
3. 프론트엔드가 result_image_url로 게시물 생성 요청 (POST /api/posts/)
4. 백엔드에서는 이미 자동으로 게시물 생성했으나, 프론트엔드는 이를 모름
5. 결과: 동일한 이미지로 2개의 게시물 생성
```

**증거**:
- 로그에 `POST /api/posts/`가 프론트엔드 요청으로 나타남 (백엔드 자동 생성은 로그에 없음)
- 백엔드의 자동 생성은 `integration_service.create_result_post()`에서 발생하지만, 이는 Flask 요청 로그에 나타나지 않음
- 프론트엔드가 `GET /api/posts/?limit=20`을 두 번 호출 (UI 업데이트 시도)

**시나리오 B: 프론트엔드 중복 호출 (네트워크 재시도 등)**
```
1. 프론트엔드가 POST /api/posts/ 요청
2. 네트워크 지연으로 응답 없음
3. 프론트엔드가 재시도 로직으로 다시 요청
4. 두 요청 모두 성공하여 2개 게시물 생성
```

**증거 부족**:
- 로그에 `POST /api/posts/`가 **한 번만** 나타남
- 이 시나리오는 가능성 낮음

---

### 🎯 최종 진단: 백엔드 자동 생성 + 프론트엔드 수동 생성

#### 실제 발생 흐름 (추정)

```
[백엔드 - ThreadPoolExecutor]
1. 작업 완료 → handle_job_completed()
2. integration_service.create_result_post() 호출
3. post_service.create_post() 실행 (첫 번째 게시물 생성) ✅
4. Firestore에 게시물 A 저장 (post_id: xxx-111)

[프론트엔드 - Polling]
5. GET /api/cartoon-jobs/{id} → status: COMPLETED, result_image_url 확인
6. 프론트엔드 로직: "작업 완료! 이제 게시물을 만들어야지"
7. POST /api/posts/ 요청 (두 번째 게시물 생성) ✅
8. Firestore에 게시물 B 저장 (post_id: yyy-222)

[프론트엔드 - UI 업데이트]
9. GET /api/posts/?limit=20 (피드 새로고침)
10. 결과: 동일한 만화 이미지를 가진 2개의 게시물 표시
```

#### 핵심 문제점
1. **백엔드**: 작업 완료 시 자동으로 게시물 생성 ✅ (의도된 동작)
2. **프론트엔드**: 작업 완료 감지 후 수동으로 게시물 생성 ❌ (불필요한 동작)
3. **동기화 부재**: 프론트엔드가 백엔드의 자동 생성 여부를 모름

---

## 🔧 해결 방안

### 방안 1: 프론트엔드 수정 (권장 ⭐)

**프론트엔드가 게시물을 직접 생성하지 않도록 수정**

```dart
// Before (추정)
Future<void> _pollCartoonJob(String jobId) async {
  while (true) {
    final job = await cartoonJobService.getJobStatus(jobId);
    
    if (job.status == CartoonJobStatus.completed) {
      // ❌ 문제: 직접 게시물 생성
      final post = await postService.createPost(
        text: job.userText,
        imagePaths: [job.resultImageUrl],
      );
      
      // 피드로 이동
      Navigator.pushNamed(context, '/feed');
      break;
    }
    
    await Future.delayed(Duration(seconds: 2));
  }
}

// After (수정)
Future<void> _pollCartoonJob(String jobId) async {
  while (true) {
    final job = await cartoonJobService.getJobStatus(jobId);
    
    if (job.status == CartoonJobStatus.completed) {
      // ✅ 해결: 게시물은 백엔드에서 자동 생성됨
      // 단순히 피드로 이동만 하면 됨
      Navigator.pushNamed(context, '/feed');
      break;
    }
    
    await Future.delayed(Duration(seconds: 2));
  }
}
```

**장점**:
- 가장 간단하고 명확한 해결책
- 백엔드 로직 변경 불필요
- 중복 생성 완전 방지

**단점**:
- 프론트엔드 코드 수정 필요

---

### 방안 2: 백엔드 응답에 post_id 포함

**백엔드 수정**: 작업 완료 응답에 생성된 게시물 ID 포함

```python
# job_service.py (update_job_status)
def update_job_status(self, job_id: str, status: CartoonJobStatus, 
                     result_data: Dict[str, Any] = None) -> Dict[str, Any]:
    # ...
    if result_data:
        update_dict.update(result_data)
        # post_id 추가 (integration_service에서 전달)
        if 'post_id' in result_data:
            update_dict['post_id'] = result_data['post_id']
    # ...

# integration_service.py (create_result_post)
def create_result_post(self, job_data: Dict[str, Any], result_image_url: str):
    # ...
    post_result = self.post_service.create_post(...)
    logging.info(f"만화 게시물 자동 생성 완료 (post_id: {post_result.get('post_id')})")
    return post_result  # post_id 포함

# event_service.py (handle_job_completed)
def handle_job_completed(self, update_data: Dict[str, Any]):
    # ...
    post_result = job_integration.create_result_post(job, result_image_url)
    
    # post_id를 작업 상태에 추가
    if post_result and post_result.get('post_id'):
        job_service.update_job_metadata(job_id, {'post_id': post_result['post_id']})
```

**프론트엔드 수정**:
```dart
Future<void> _pollCartoonJob(String jobId) async {
  while (true) {
    final job = await cartoonJobService.getJobStatus(jobId);
    
    if (job.status == CartoonJobStatus.completed) {
      if (job.postId != null) {
        // ✅ 백엔드에서 이미 게시물 생성됨
        Navigator.pushNamed(
          context,
          '/post-detail',
          arguments: {'postId': job.postId},
        );
      } else {
        // 백엔드 자동 생성 실패 시 수동 생성
        final post = await postService.createPost(...);
        Navigator.pushNamed(context, '/feed');
      }
      break;
    }
    
    await Future.delayed(Duration(seconds: 2));
  }
}
```

**장점**:
- 프론트엔드가 백엔드의 자동 생성 여부를 명확히 알 수 있음
- 자동 생성 실패 시 폴백 로직 가능
- 생성된 게시물로 바로 이동 가능 (UX 향상)

**단점**:
- 백엔드 및 프론트엔드 모두 수정 필요
- 스키마 변경 필요 (`CartoonJobResponseSchema`에 `post_id` 추가)

---

### 방안 3: 멱등성 키 사용 (부분 해결)

**프론트엔드가 게시물 생성 시 멱등성 키 사용**

```dart
Future<void> _pollCartoonJob(String jobId) async {
  while (true) {
    final job = await cartoonJobService.getJobStatus(jobId);
    
    if (job.status == CartoonJobStatus.completed) {
      // 작업 ID를 멱등성 키로 사용
      final post = await postService.createPost(
        text: job.userText,
        imagePaths: [job.resultImageUrl],
        idempotencyKey: 'cartoon-job-${jobId}',  // ← 멱등성 키
      );
      
      Navigator.pushNamed(context, '/feed');
      break;
    }
    
    await Future.delayed(Duration(seconds: 2));
  }
}
```

**문제점**:
- 백엔드 자동 생성과 프론트엔드 수동 생성은 서로 다른 요청 컨텍스트
- 멱등성 키가 달라서 중복 방지 불가능
- **이 방안은 효과 없음** ❌

---

### 방안 4: 백엔드 자동 생성 제거 (비권장)

**백엔드에서 자동 게시물 생성 로직 제거**

```python
# event_service.py (handle_job_completed)
def handle_job_completed(self, update_data: Dict[str, Any]):
    # ...
    # ❌ 주석 처리
    # post_result = job_integration.create_result_post(job, result_image_url)
    
    # 알림만 발송
    job_integration.send_completion_notification(user_id, job_id, post_result=None)
```

**장점**:
- 프론트엔드가 게시물 생성 타이밍 완전 제어
- 사용자가 게시물 텍스트를 수정할 기회 제공 가능

**단점**:
- 기존 설계 의도와 다름 (자동 업로드가 주요 기능)
- 사용자 경험 저하 (추가 단계 필요)
- 프론트엔드 코드 수정 필요

---

## 📊 비동기 처리 분석

### 프론트엔드 동기 처리 의문

**질문**: "프론트엔드가 코루틴을 사용하지 않고 동기로 처리했을까?"

#### Flutter의 비동기 처리
```dart
// Flutter는 기본적으로 async/await 사용 (Dart 언어)
Future<void> _pollCartoonJob(String jobId) async {
  // async/await는 코루틴과 유사한 개념
  final job = await cartoonJobService.getJobStatus(jobId);
  
  // while 루프 + await는 실제로 비동기 polling
  while (job.status != CartoonJobStatus.completed) {
    await Future.delayed(Duration(seconds: 2));
    job = await cartoonJobService.getJobStatus(jobId);
  }
}
```

**답변**:
- Flutter(Dart)는 `async/await` 문법 사용 (JavaScript의 Promise와 유사)
- 이는 Python의 `asyncio` 코루틴과 개념적으로 동일
- `await Future.delayed()`는 Non-blocking delay (이벤트 루프에서 대기)
- **프론트엔드는 비동기로 처리 중** ✅

#### 로그에서 확인되는 polling
```
11:29:09 - GET /api/cartoon-jobs/8df5... (첫 번째 polling)
11:29:11 - GET /api/cartoon-jobs/8df5... (2초 후)
11:29:14 - GET /api/cartoon-jobs/8df5... (3초 후, 약간의 지연)
...
11:29:56 - GET /api/cartoon-jobs/8df5... (마지막 polling)
```

**관찰**:
- 약 2초 간격으로 polling (일부 3-4초 간격도 있음)
- 네트워크 지연 + 백엔드 처리 시간 포함
- 총 47초 동안 약 24회 polling

---

## ✅ 권장 해결 방안 요약

### 우선순위 1: 프론트엔드 수정 (즉시 적용 가능)

**수정 사항**:
1. **게시물 직접 생성 로직 제거**
   - 작업 완료 후 `postService.createPost()` 호출 제거
   - 백엔드가 자동으로 생성한 게시물을 신뢰

2. **UI 흐름 단순화**
   - 작업 완료 → 피드로 이동
   - 새로 생성된 게시물은 피드 최상단에 자동 표시

```dart
// 수정 예시
if (job.status == CartoonJobStatus.completed) {
  // ❌ 제거: await postService.createPost(...)
  // ✅ 추가: 단순히 피드로 이동
  Navigator.pushNamed(context, '/feed');
  
  // 선택사항: 성공 토스트 메시지
  showToast('만화가 게시물로 자동 업로드되었습니다!');
}
```

### 우선순위 2: 백엔드 개선 (선택사항)

**추가 기능**:
1. `CartoonJobResponseSchema`에 `post_id` 필드 추가
2. 작업 완료 응답에 생성된 게시물 ID 포함
3. 프론트엔드에서 게시물 상세 페이지로 바로 이동 가능

```python
# schemas.py
class CartoonJobResponseSchema(Schema):
    job_id = fields.Str(required=True)
    # ...
    post_id = fields.Str(allow_none=True)  # ← 추가
```

---

## 🔍 디버깅 체크리스트

### 백엔드 확인
- [ ] `integration_service.create_result_post()` 로그 확인
  - `logging.info(f"만화 게시물 자동 생성 완료 (post_id: {post_result.get('post_id')})")`
  - 이 로그가 나타나면 백엔드에서 게시물 생성 중

- [ ] Firestore `posts` 컬렉션 확인
  - 동일한 `result_image_url`을 가진 게시물이 2개인지 확인
  - `created_at` 타임스탬프 차이 확인 (몇 초 차이인지)

- [ ] Firestore `cartoon_jobs` 컬렉션 확인
  - `status: COMPLETED` 상태의 작업 확인
  - `result_image_url` 필드 존재 여부

### 프론트엔드 확인
- [ ] 작업 완료 처리 로직 확인
  ```dart
  if (job.status == CartoonJobStatus.completed) {
    // 이 블록에서 postService.createPost() 호출하는지 확인
  }
  ```

- [ ] 네트워크 로그 확인 (개발자 도구)
  - `POST /api/posts/` 요청이 몇 번 발생하는지
  - 요청 body에 동일한 `file_paths`가 있는지

---

## 📚 관련 문서
- [CARTOON_JOB_FIX_SUMMARY.md](./CARTOON_JOB_FIX_SUMMARY.md): 이전 만화 작업 수정 내역
- [CARTOON_JOB_DEBUGGING.md](./CARTOON_JOB_DEBUGGING.md): 만화 작업 디버깅 가이드
- [DEEPLINKS_AND_IDEMPOTENCY.md](../DEEPLINKS_AND_IDEMPOTENCY.md): 멱등성 관련 문서

---

**작성일**: 2025-10-15  
**상태**: 분석 완료, 해결 방안 제시  
**다음 단계**: 프론트엔드 코드 확인 및 수정
