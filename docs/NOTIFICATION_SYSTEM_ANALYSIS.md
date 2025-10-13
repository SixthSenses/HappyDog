# HappyDog 알림(Notification) 시스템 분석 문서

**작성일**: 2025-10-13  
**목적**: 알림 수신 설정, 기본값, 발생 도메인 및 전체 흐름 체계화

---

## 📋 목차

1. [시스템 개요](#1-시스템-개요)
2. [알림 타입 정의](#2-알림-타입-정의)
3. [알림 수신 설정 (User Preferences)](#3-알림-수신-설정-user-preferences)
4. [알림 발생 도메인별 분석](#4-알림-발생-도메인별-분석)
5. [알림 생성 흐름](#5-알림-생성-흐름)
6. [푸시 알림 (FCM) 시스템](#6-푸시-알림-fcm-시스템)
7. [알림 조회 및 관리 API](#7-알림-조회-및-관리-api)
8. [데이터 모델](#8-데이터-모델)
9. [설정 가이드](#9-설정-가이드)

---

## 1. 시스템 개요

### 아키텍처 구성

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Domain Layer   │─────>│ Notification     │─────>│  Firestore      │
│  (Posts,        │      │ Service          │      │  (notifications)│
│   Comments,     │      │ (Core)           │      └─────────────────┘
│   CartoonJobs)  │      └──────────────────┘              │
└─────────────────┘              │                         │
                                 │                         ▼
                                 ▼                  ┌─────────────────┐
                        ┌──────────────────┐       │  User Doc       │
                        │  FCM Push        │       │  (preferences,  │
                        │  (Firebase       │       │   fcm_token)    │
                        │   Messaging)     │       └─────────────────┘
                        └──────────────────┘
```

### 핵심 컴포넌트

| 컴포넌트 | 위치 | 역할 |
|---------|------|------|
| **NotificationService** | `app/services/notification_service.py` | 알림 생성, FCM 푸시, 설정 검증 |
| **NotificationType (Enum)** | `app/models/notification.py` | 알림 타입 정의 |
| **User Preferences** | Firestore `users/{user_id}.notification_preferences` | 사용자별 알림 수신 설정 |
| **NotificationConfig** | `app/api/notifications/config.py` | 메시지 템플릿, 딥링크, 우선순위 |
| **Domain Services** | `app/api/*/services/*_service.py` | 각 도메인에서 알림 트리거 |

---

## 2. 알림 타입 정의

### NotificationType Enum

```python
# app/models/notification.py
class NotificationType(Enum):
    # 소셜 인터랙션 (Social Interactions)
    POST_LIKE = "POST_LIKE"              # 게시글 좋아요
    COMMENT_LIKE = "COMMENT_LIKE"        # 댓글 좋아요
    COMMENT = "COMMENT"                  # 게시글에 댓글 작성
    MENTION = "MENTION"                  # 댓글에서 @멘션
    
    # 카툰 작업 (Cartoon Jobs)
    CARTOON_SUCCESS = "CARTOON_SUCCESS"  # 카툰 생성 성공
    CARTOON_FAILED = "CARTOON_FAILED"    # 카툰 생성 실패
    CARTOON_PROGRESS = "CARTOON_PROGRESS"  # (예약) 카툰 작업 진행 중
    CARTOON_COMPLETED = "CARTOON_COMPLETED" # (예약) 카툰 작업 완료
    
    # 펫케어 (Pet Care) - 예약 타입
    PET_CARE_GOAL_REACHED = "PET_CARE_GOAL_REACHED"     # 목표 달성
    PET_CARE_DAILY_SUMMARY = "PET_CARE_DAILY_SUMMARY"   # 일일 요약
```

### 알림 타입별 특성

| 타입 | 우선순위 | Sender 필요 | Summary 필요 | 딥링크 대상 |
|-----|---------|------------|-------------|-----------|
| **POST_LIKE** | low | ✅ Yes | ❌ No | `app://posts/{post_id}` |
| **COMMENT_LIKE** | low | ✅ Yes | ✅ Yes | `app://comments/{comment_id}` |
| **COMMENT** | normal | ✅ Yes | ✅ Yes | `app://posts/{post_id}` |
| **MENTION** | high | ✅ Yes | ✅ Yes | `app://posts/{post_id}` |
| **CARTOON_SUCCESS** | normal | ❌ No (system) | ✅ Yes | `app://cartoon-jobs/{job_id}` or `app://posts/{post_id}` |
| **CARTOON_FAILED** | high | ❌ No (system) | ✅ Yes | `app://cartoon-jobs/{job_id}` |
| **PET_CARE_GOAL_REACHED** | normal | ❌ No (system) | ❌ No | `app://pet-care/dashboard` |

### 메시지 템플릿 (한국어)

```python
# app/api/notifications/config.py
MESSAGE_TEMPLATES = {
    'ko': {
        'COMMENT': '{sender}님이 댓글을 남겼습니다: {summary}',
        'POST_LIKE': '{sender}님이 게시물을 좋아합니다',
        'COMMENT_LIKE': '{sender}님이 댓글을 좋아합니다: {summary}',
        'MENTION': '{sender}님이 나를 언급했습니다: {summary}',
        'CARTOON_SUCCESS': '카툰 생성이 완료되었습니다',
        'CARTOON_FAILED': '카툰 생성에 실패했습니다',
        'PET_CARE_GOAL_REACHED': '오늘 목표를 달성했어요!',
    }
}

TITLE_TEMPLATES = {
    'ko': {
        'COMMENT': '새로운 댓글',
        'POST_LIKE': '새로운 좋아요',
        'COMMENT_LIKE': '새로운 좋아요',
        'MENTION': '나를 언급했어요',
        'CARTOON_SUCCESS': '카툰 작업 완료',
        'CARTOON_FAILED': '카툰 작업 실패',
    }
}
```

---

## 3. 알림 수신 설정 (User Preferences)

### 3.1 데이터 구조

Firestore `users/{user_id}` 문서 내 `notification_preferences` 필드:

```json
{
  "notification_preferences": {
    "mode": "both",
    "types": {
      "POST_LIKE": true,
      "COMMENT_LIKE": true,
      "COMMENT": true,
      "MENTION": true,
      "CARTOON_SUCCESS": true,
      "CARTOON_FAILED": true,
      "PET_CARE_GOAL_REACHED": true
    }
  }
}
```

### 3.2 설정 필드 설명

| 필드 | 타입 | 설명 | 기본값 |
|-----|------|------|-------|
| **mode** | `string` | 알림 전송 방식<br>- `"inapp"`: 인앱 알림만<br>- `"push"`: 푸시 알림만<br>- `"both"`: 둘 다<br>- `null` 또는 미설정: 서비스 기본값(`"both"`) 사용 | `"both"` |
| **types** | `object` | 알림 타입별 수신 on/off<br>- Key: `NotificationType` 문자열<br>- Value: `true` (수신) / `false` (차단) | 모두 `true` |

### 3.3 기본값 정책

#### 신규 사용자 기본값
```python
# app/api/auth/services/auth_service.py (신규 사용자 생성 시)
DEFAULT_NOTIFICATION_PREFERENCES = {
    "mode": "both",
    "types": {
        "POST_LIKE": True,
        "COMMENT_LIKE": True,
        "COMMENT": True,
        "MENTION": True,
        "CARTOON_SUCCESS": True,
        "CARTOON_FAILED": True,
        "PET_CARE_GOAL_REACHED": True,
        "PET_CARE_DAILY_SUMMARY": True
    }
}
```

**결정 이유:**
- ✅ **Opt-out 방식**: 모든 알림을 기본 활성화하여 사용자가 중요한 알림을 놓치지 않도록 함
- ✅ **사용자 제어**: 원하지 않는 알림은 설정에서 개별적으로 비활성화 가능
- ✅ **푸시 권한 별도**: FCM 푸시는 OS 레벨 권한이 필요하므로 별도 관리

#### 설정 미지정 시 동작
```python
# app/services/notification_service.py
def create_notification(...):
    # 1. User document에서 notification_preferences 로드
    recipient_prefs = (recipient_info.get('notification_preferences') or {})
    types_prefs = recipient_prefs.get('types') or {}
    
    # 2. 특정 타입 차단 여부 확인
    type_key = n_type.value  # 예: "POST_LIKE"
    if type_key in types_prefs and not types_prefs[type_key]:
        # 사용자가 명시적으로 이 타입을 차단함
        logging.info(f"알림 차단됨(type={type_key}, recipient={recipient_id})")
        return
    
    # 3. types_prefs에 없으면 기본값(True) 적용 → 알림 생성
```

**동작 시나리오:**
| 설정 상태 | `types.POST_LIKE` 값 | 결과 |
|----------|---------------------|------|
| 설정 없음 (신규 유저) | `undefined` | ✅ 알림 생성 (기본값 허용) |
| `{"POST_LIKE": true}` | `true` | ✅ 알림 생성 |
| `{"POST_LIKE": false}` | `false` | ❌ 알림 차단 |
| `types` 필드 자체가 없음 | `undefined` | ✅ 알림 생성 (기본값 허용) |

### 3.4 알림 설정 API

#### GET /api/users/me/notification-preferences
```http
GET /api/users/me/notification-preferences
Authorization: Bearer {access_token}

Response 200:
{
  "mode": "both",
  "types": {
    "POST_LIKE": true,
    "COMMENT": true,
    ...
  }
}
```

#### PUT /api/users/me/notification-preferences
```http
PUT /api/users/me/notification-preferences
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "mode": "push",
  "types": {
    "POST_LIKE": false,
    "COMMENT": true
  }
}

Response 200:
{
  "mode": "push",
  "types": {
    "POST_LIKE": false,
    "COMMENT": true
  }
}
```

**주의사항:**
- ✅ `types` 필드는 **부분 업데이트 불가** - 전체 타입 목록을 전송해야 함
- ✅ 명시되지 않은 타입은 **기본값(true)으로 초기화**되지 않고, 기존 값 유지 또는 삭제됨
- ⚠️ 프론트엔드는 현재 설정을 GET으로 먼저 조회한 후 수정하여 PUT 권장

---

## 4. 알림 발생 도메인별 분석

### 4.1 Posts 도메인 (게시글)

#### 발생 이벤트

| 이벤트 | 알림 타입 | 트리거 위치 | 수신자 |
|-------|---------|-----------|-------|
| **게시글 좋아요** | `POST_LIKE` | `app/api/posts/services/event_service.py`<br>`handle_post_liked()` | 게시글 작성자 |

#### 코드 흐름

```python
# app/api/posts/routes.py
@posts_bp.route('/<string:post_id>/like', methods=['POST'])
def toggle_post_like(post_id: str):
    # 1. 좋아요 토글 처리
    result = post_service.toggle_post_like(user_id, post_id)
    
    # 2. 이벤트 발행
    if result['action'] == 'liked':
        post_event_service.handle_post_liked({
            'user_id': user_id,
            'post_id': post_id,
            'post_author_id': result['post_author_id'],
            'action': 'liked'
        })
```

```python
# app/api/posts/services/event_service.py
def handle_post_liked(self, like_data: Dict[str, Any]) -> None:
    # 자기 자신에게 알림 보내지 않음
    if post_author_id == user_id:
        return
    
    notification_service = current_app.services.get('notifications')
    notification_service.create_notification(
        recipient_id=post_author_id,  # 게시글 작성자
        sender_id=user_id,             # 좋아요 누른 사람
        n_type=NotificationType.POST_LIKE,
        target_id=post_id              # 게시글 ID
    )
```

### 4.2 Comments 도메인 (댓글)

#### 발생 이벤트

| 이벤트 | 알림 타입 | 트리거 위치 | 수신자 |
|-------|---------|-----------|-------|
| **댓글 작성** | `COMMENT` | `app/api/comments/services/notification_service.py`<br>`notify_post_author()` | 게시글 작성자 |
| **댓글에 @멘션** | `MENTION` | `app/api/comments/services/notification_service.py`<br>`notify_mentioned_users()` | 멘션된 사용자들 |
| **댓글 좋아요** | `COMMENT_LIKE` | `app/api/comments/services/notification_service.py`<br>`notify_comment_liked()` | 댓글 작성자 |

#### 코드 흐름 - 댓글 작성

```python
# app/api/comments/routes.py
@comments_bp.route('/', methods=['POST'])
def create_comment():
    # 1. 댓글 생성
    new_comment = comment_service.create_comment(user_id, validated_data)
    
    # 2. 멘션 사용자 추출
    mentioned_user_ids = comment_service.extract_mentioned_users(validated_data['text'])
    
    # 3. 알림 생성 (게시글 작성자)
    comment_notification_service.notify_post_author({
        'comment_id': new_comment['comment_id'],
        'post_id': validated_data['post_id'],
        'comment_author_id': user_id,
        'post_author_id': post_author_id,  # 게시글 작성자
        'comment_text': validated_data['text']
    })
    
    # 4. 멘션 알림 생성
    if mentioned_user_ids:
        comment_notification_service.notify_mentioned_users({
            'comment_id': new_comment['comment_id'],
            'post_id': validated_data['post_id'],
            'comment_author_id': user_id,
            'mentioned_user_ids': mentioned_user_ids,
            'comment_text': validated_data['text']
        })
```

#### 멘션 추출 로직

```python
# app/api/comments/services/comment_service.py
def extract_mentioned_users(self, text: str) -> List[str]:
    """
    댓글 텍스트에서 @nickname 형태의 멘션을 추출하여 user_id 리스트로 변환
    
    예시:
      "@철수 @영희 안녕하세요" → ['user123', 'user456']
    """
    pattern = r'@([a-zA-Z0-9가-힣_]+)'
    nicknames = re.findall(pattern, text)
    
    # nickname → user_id 매핑
    user_ids = []
    for nickname in nicknames:
        user_doc = self.users_ref.where('nickname', '==', nickname).limit(1).stream()
        for doc in user_doc:
            user_ids.append(doc.id)
    
    return user_ids
```

### 4.3 Cartoon Jobs 도메인 (카툰 생성)

#### 발생 이벤트

| 이벤트 | 알림 타입 | 트리거 위치 | 수신자 |
|-------|---------|-----------|-------|
| **카툰 생성 성공** | `CARTOON_SUCCESS` | `app/api/cartoon_jobs/services/integration_service.py`<br>`send_completion_notification()` | 작업 요청자 |
| **카툰 생성 실패** | `CARTOON_FAILED` | `app/api/cartoon_jobs/services/integration_service.py`<br>`send_failure_notification()` | 작업 요청자 |

#### 코드 흐름

```python
# app/api/cartoon_jobs/services/integration_service.py
def send_completion_notification(self, user_id: str, job_id: str, 
                                post_result: Optional[Dict] = None):
    # 게시물 생성 성공 여부에 따라 메시지 분기
    if post_result and post_result.get('post_id'):
        target_summary = "만화 생성이 완료되어 게시물로 자동 업로드되었습니다."
        target_id = post_result['post_id']  # 딥링크: 게시물로 이동
    else:
        target_summary = "만화 생성이 완료되었습니다."
        target_id = job_id  # 딥링크: 작업 상세로 이동
    
    self.notification_service.create_notification(
        recipient_id=user_id,
        sender_id="system",  # 시스템 알림
        n_type=NotificationType.CARTOON_SUCCESS,
        target_id=target_id,
        target_summary=target_summary
    )

def send_failure_notification(self, user_id: str, job_id: str, error_message: str):
    # 사용자 친화적 에러 메시지 변환
    user_friendly_message = self._get_user_friendly_error_message(error_message)
    
    self.notification_service.create_notification(
        recipient_id=user_id,
        sender_id="system",
        n_type=NotificationType.CARTOON_FAILED,
        target_id=job_id,
        target_summary=user_friendly_message
    )
```

**에러 메시지 변환 예시:**
```python
def _get_user_friendly_error_message(self, error_message: str) -> str:
    error_lower = error_message.lower()
    
    if "timeout" in error_lower:
        return "만화 생성에 시간이 오래 걸려 작업이 중단되었습니다."
    elif "api" in error_lower and "limit" in error_lower:
        return "서비스 사용량이 많아 일시적으로 처리할 수 없습니다."
    elif "network" in error_lower:
        return "네트워크 연결 문제로 만화 생성에 실패했습니다."
    else:
        return "만화 생성 중 오류가 발생했습니다. 다시 시도해주세요."
```

### 4.4 Pet Care 도메인 (펫케어) - 예약 타입

현재 **구현되지 않음**. 향후 확장 가능:

```python
# 예시: app/api/pet_care/records/notifier.py (미구현)
def notify_goal_reached(self, user_id: str, pet_id: str, date: str, metric: str):
    """목표 달성 알림 (예약 기능)"""
    self.notification_service.create_notification(
        recipient_id=user_id,
        sender_id="system",
        n_type=NotificationType.PET_CARE_GOAL_REACHED,
        target_id=pet_id,
        target_summary=f"{date} {metric} 목표 달성!"
    )
```

---

## 5. 알림 생성 흐름

### 5.1 NotificationService.create_notification()

```python
# app/services/notification_service.py
def create_notification(self, recipient_id: str, sender_id: str, 
                       n_type: NotificationType, target_id: str, 
                       target_summary: Optional[str] = None,
                       delivery: Optional[str] = None):
    """
    중앙화된 알림 생성 로직
    
    처리 단계:
    1. 자기 자신 알림 차단
    2. 수신자 설정 검증 (notification_preferences)
    3. 발신자 정보 구성
    4. Notification 객체 생성 및 Firestore 저장
    5. 미확인 카운터 증분 (notification_unread_count)
    6. 푸시 알림 전송 (FCM)
    """
```

### 5.2 단계별 처리 상세

#### Step 1: 자기 자신 알림 차단
```python
if recipient_id == sender_id:
    return  # 자기 게시물에 자기가 좋아요 → 알림 X
```

#### Step 2: 수신자 설정 검증
```python
# Firestore에서 수신자 정보 조회
recipient_doc = self.users_ref.document(recipient_id).get()
if not recipient_doc.exists:
    logging.warning(f"수신자 없음: {recipient_id}")
    return

recipient_info = recipient_doc.to_dict()
recipient_prefs = (recipient_info.get('notification_preferences') or {})
types_prefs = recipient_prefs.get('types') or {}

# 타입별 수신 설정 확인
type_key = n_type.value  # 예: "POST_LIKE"
if type_key in types_prefs and not types_prefs[type_key]:
    logging.info(f"알림 차단됨(type={type_key})")
    return  # 사용자가 이 타입 알림 비활성화
```

#### Step 3: 발신자 정보 구성
```python
if sender_id == "system":
    sender_data = {
        "user_id": "system",
        "nickname": "HappyDog",
        "profile_image_url": None
    }
else:
    sender_doc = self.users_ref.document(sender_id).get()
    sender_info = sender_doc.to_dict()
    sender_data = {
        "user_id": sender_info.get('user_id'),
        "nickname": sender_info.get('nickname'),
        "profile_image_url": sender_info.get('profile_image_url')
    }
```

#### Step 4: Notification 저장
```python
notification = Notification(
    notification_id=str(uuid.uuid4()),
    recipient_id=recipient_id,
    sender=sender_data,
    type=n_type,
    target_id=target_id,
    target_summary=truncate_summary(target_summary),
    is_read=False,
    created_at=DateTimeUtils.now()
)

# Firestore에 저장
notification_dict = asdict(notification)
notification_dict['type'] = notification.type.value
self.notifications_ref.document(notification.notification_id).set(notification_dict)

# 미확인 카운터 증분
self.users_ref.document(recipient_id).update({
    'notification_unread_count': firestore.Increment(1)
})
```

#### Step 5: 푸시 알림 전송
```python
# 사용자 mode 설정 확인
user_mode = (recipient_prefs.get('mode') or '').lower()
delivery_policy = (user_mode or (delivery or self.default_delivery)).lower()

if delivery_policy in ("push", "both"):
    token = recipient_info.get('fcm_token')
    if token:
        success, reason = self._send_push_notification_with_token(token, notification)
        if not success and reason in ('unregistered', 'invalid-argument'):
            # 무효 토큰 제거
            self.users_ref.document(recipient_id).update({
                'fcm_token': firestore.DELETE_FIELD
            })
```

---

## 6. 푸시 알림 (FCM) 시스템

### 6.1 FCM 토큰 관리

#### 토큰 등록/업데이트
```http
PUT /api/users/me/fcm-token
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "fcm_token": "fT7K3...xB2pQ"
}

Response 200:
{
  "message": "FCM 토큰이 업데이트되었습니다."
}
```

#### 토큰 저장 위치
```
Firestore: users/{user_id}
{
  "fcm_token": "fT7K3...xB2pQ",  // 클라이언트 디바이스 토큰
  "notification_preferences": { ... }
}
```

### 6.2 푸시 전송 로직

```python
# app/services/notification_service.py
def _send_push_notification_with_token(self, token: str, notification: Notification):
    """
    FCM 푸시 메시지 전송
    
    Returns:
        (success: bool, reason: Optional[str])
    """
    # 메시지 빌드
    title = self._build_title(notification)  # "새로운 댓글"
    body = self._build_body(notification)    # "철수님이 댓글을 남겼습니다: 안녕하세요"
    
    message = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=title,
            body=body
        ),
        data={
            'notification_id': notification.notification_id,
            'type': notification.type.value,
            'target_id': notification.target_id,
            'deeplink': self._build_deeplink(notification)
        }
    )
    
    try:
        response = messaging.send(message)
        return True, None
    except Exception as e:
        reason = self._classify_push_error(e)
        return False, reason
```

### 6.3 푸시 에러 처리

```python
def _classify_push_error(self, exc: Exception) -> str:
    """
    FCM 에러 분류
    
    에러 타입:
    - 'unregistered': 토큰이 더 이상 유효하지 않음 → 토큰 삭제
    - 'invalid-argument': 토큰 형식 오류 → 토큰 삭제
    - 'mismatch-sender': 잘못된 Sender ID
    - 'other': 기타 에러 (재시도 가능)
    """
    msg = str(exc).lower()
    
    if 'unregistered' in msg or 'registration-token-not-registered' in msg:
        return 'unregistered'
    if 'invalidargument' in msg or 'invalid registration' in msg:
        return 'invalid-argument'
    if 'mismatchsenderid' in msg:
        return 'mismatch-sender'
    
    return 'other'
```

**무효 토큰 자동 제거:**
```python
if reason in ('unregistered', 'invalid-argument'):
    # Firestore에서 토큰 필드 삭제
    self.users_ref.document(recipient_id).update({
        'fcm_token': firestore.DELETE_FIELD
    })
    logging.info(f"무효 FCM 토큰 제거: {recipient_id}")
```

### 6.4 푸시 메시지 구성

#### 타이틀 생성
```python
def _build_title(self, n: Notification) -> str:
    """
    알림 타입별 타이틀 생성
    
    예시:
    - POST_LIKE → "새로운 좋아요"
    - COMMENT → "새로운 댓글"
    - CARTOON_SUCCESS → "카툰 작업 완료"
    """
    from app.api.notifications.handlers import NotificationHandlerFactory
    handler = NotificationHandlerFactory.get_handler(n.type.value)
    return handler.get_title()
```

#### 본문 생성
```python
def _build_body(self, n: Notification) -> str:
    """
    알림 타입 및 발신자 정보를 조합하여 메시지 본문 생성
    
    예시:
    - POST_LIKE: "철수님이 게시물을 좋아합니다"
    - COMMENT: "영희님이 댓글을 남겼습니다: 안녕하세요"
    """
    handler = NotificationHandlerFactory.get_handler(n.type.value)
    return handler.format_message(n, format_type='mobile')
```

#### 딥링크 생성
```python
def _build_deeplink(self, n: Notification) -> str:
    """
    알림 타입별 딥링크 URL 생성
    
    예시:
    - POST_LIKE → "app://posts/post123"
    - COMMENT → "app://posts/post456"
    - CARTOON_SUCCESS → "app://cartoon-jobs/job789" or "app://posts/post999"
    """
    handler = NotificationHandlerFactory.get_handler(n.type.value)
    return handler.get_deeplink(n)
```

---

## 7. 알림 조회 및 관리 API

### 7.1 알림 목록 조회

```http
GET /api/notifications?limit=20&cursor=noti123&format=mobile
Authorization: Bearer {access_token}

Response 200:
{
  "items": [
    {
      "notification_id": "noti456",
      "type": "COMMENT",
      "sender": {
        "user_id": "user123",
        "nickname": "철수",
        "profile_image_url": "https://..."
      },
      "target_id": "post789",
      "target_summary": "안녕하세요",
      "message": "철수님이 댓글을 남겼습니다: 안녕하세요",
      "deeplink": "app://posts/post789",
      "is_read": false,
      "created_at": "2025-10-13T10:30:00Z"
    }
  ],
  "meta": {
    "next_cursor": "noti789",
    "has_more": true
  }
}
```

**Query Parameters:**
- `limit` (optional, default=20): 한 번에 가져올 알림 수 (1~50)
- `cursor` (optional): 페이지네이션 커서
- `format` (optional, default=web): `mobile` 또는 `web` (메시지 길이 제한 다름)

### 7.2 알림 확인 처리

```http
POST /api/notifications/{notification_id}/ack
Authorization: Bearer {access_token}
X-Idempotency-Key: {unique_key}

Response 200:
{
  "status": "ok"
}
```

**동작:**
1. `is_read` 필드를 `true`로 업데이트
2. `notification_unread_count` 카운터 감소 (Firestore Increment(-1))
3. 이미 읽은 알림이면 noop (중복 처리 방지)

### 7.3 미확인 알림 수 조회

```http
GET /api/notifications/unread-count
Authorization: Bearer {access_token}

Response 200:
{
  "unread_count": 5
}
```

**구현 방식:**
```python
# app/services/notification_service.py
def get_unread_count(self, user_id: str) -> int:
    """
    미확인 알림 개수 조회
    
    방법 1 (현재): Firestore 쿼리로 집계
      query = notifications.where('recipient_id', '==', user_id)
                          .where('is_read', '==', False)
      return sum(1 for _ in query.stream())
    
    방법 2 (최적화): User 문서의 카운터 필드 사용
      return users.document(user_id).get().to_dict().get('notification_unread_count', 0)
    """
```

---

## 8. 데이터 모델

### 8.1 Notification 컬렉션 (Firestore)

```
Collection: notifications/{notification_id}

{
  "notification_id": "uuid-string",
  "recipient_id": "user123",
  "sender": {
    "user_id": "user456" | "system",
    "nickname": "철수" | "HappyDog",
    "profile_image_url": "https://..." | null
  },
  "type": "COMMENT" | "POST_LIKE" | "CARTOON_SUCCESS" | ...,
  "target_id": "post789",
  "target_summary": "안녕하세요" | null,
  "is_read": false,
  "created_at": Timestamp(2025-10-13 10:30:00)
}
```

**인덱스:**
```
- recipient_id (ASC) + created_at (DESC)  → 목록 조회
- recipient_id (ASC) + is_read (ASC)      → 미확인 알림 조회
```

### 8.2 User 문서 (Firestore)

```
Collection: users/{user_id}

{
  "user_id": "user123",
  "email": "user@example.com",
  "nickname": "철수",
  "fcm_token": "fT7K3...xB2pQ",
  "notification_unread_count": 5,
  "notification_preferences": {
    "mode": "both",
    "types": {
      "POST_LIKE": true,
      "COMMENT": true,
      "MENTION": true,
      "CARTOON_SUCCESS": true
    }
  }
}
```

### 8.3 Notification 데이터클래스

```python
# app/models/notification.py
@dataclass
class Notification:
    notification_id: str
    recipient_id: str
    sender: Dict[str, Any]  # {user_id, nickname, profile_image_url}
    type: NotificationType
    target_id: str
    target_summary: Optional[str] = None
    is_read: bool = False
    created_at: datetime = field(default_factory=DateTimeUtils.now)
```

---

## 9. 설정 가이드

### 9.1 신규 알림 타입 추가 절차

#### Step 1: Enum에 타입 추가
```python
# app/models/notification.py
class NotificationType(Enum):
    # 기존 타입들...
    NEW_FEATURE = "NEW_FEATURE"  # 새로운 알림 타입
```

#### Step 2: Config에 설정 추가
```python
# app/api/notifications/config.py
TYPE_CONFIGS = {
    'NEW_FEATURE': {
        'priority': 'normal',
        'requires_sender': True,
        'requires_summary': False
    }
}

MESSAGE_TEMPLATES = {
    'ko': {
        'NEW_FEATURE': '{sender}님이 새로운 기능을 사용했습니다'
    }
}

TITLE_TEMPLATES = {
    'ko': {
        'NEW_FEATURE': '새로운 기능 알림'
    }
}
```

#### Step 3: Handler 생성 (선택)
```python
# app/api/notifications/handlers.py
class NewFeatureNotificationHandler(BaseNotificationHandler):
    def __init__(self):
        super().__init__('NEW_FEATURE')
    
    def get_deeplink(self, notification: Notification) -> str:
        return f"app://features/{notification.target_id}"
```

#### Step 4: 기본 설정에 추가
```python
# app/api/auth/services/auth_service.py
DEFAULT_NOTIFICATION_PREFERENCES = {
    "types": {
        # 기존 타입들...
        "NEW_FEATURE": True  # 새 타입 기본값
    }
}
```

### 9.2 클라이언트 구현 가이드

#### FCM 토큰 등록 플로우
```typescript
// 1. Firebase SDK 초기화 (앱 시작 시)
import { getMessaging, getToken } from 'firebase/messaging';

const messaging = getMessaging();

// 2. 푸시 권한 요청 및 토큰 취득
async function requestNotificationPermission() {
  const permission = await Notification.requestPermission();
  
  if (permission === 'granted') {
    const token = await getToken(messaging, {
      vapidKey: 'YOUR_VAPID_KEY'
    });
    
    // 3. 서버에 토큰 등록
    await fetch('/api/users/me/fcm-token', {
      method: 'PUT',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ fcm_token: token })
    });
  }
}
```

#### 알림 설정 UI 예시
```typescript
// 알림 설정 조회
const getNotificationPreferences = async () => {
  const response = await fetch('/api/users/me/notification-preferences', {
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });
  return await response.json();
};

// 알림 설정 업데이트
const updateNotificationPreferences = async (prefs) => {
  await fetch('/api/users/me/notification-preferences', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(prefs)
  });
};

// 사용 예시
const prefs = await getNotificationPreferences();
prefs.types.POST_LIKE = false;  // 좋아요 알림 끄기
await updateNotificationPreferences(prefs);
```

#### 딥링크 처리
```typescript
// FCM 메시지 수신 시
onMessage(messaging, (payload) => {
  const { data } = payload;
  
  // 딥링크 파싱
  const deeplink = data.deeplink; // "app://posts/post123"
  
  // 화면 이동
  if (deeplink.startsWith('app://posts/')) {
    const postId = deeplink.split('/').pop();
    router.push(`/posts/${postId}`);
  } else if (deeplink.startsWith('app://cartoon-jobs/')) {
    const jobId = deeplink.split('/').pop();
    router.push(`/cartoon-jobs/${jobId}`);
  }
});
```

### 9.3 테스트 시나리오

#### 시나리오 1: 게시글 좋아요 알림
```bash
# 사용자 A: 게시글 작성
POST /api/posts
Authorization: Bearer {user_a_token}
{
  "text": "안녕하세요",
  "file_paths": []
}
# Response: { "post_id": "post123" }

# 사용자 B: 좋아요 누르기
POST /api/posts/post123/like
Authorization: Bearer {user_b_token}

# 확인: 사용자 A의 알림 목록
GET /api/notifications
Authorization: Bearer {user_a_token}
# Response: [{ "type": "POST_LIKE", "sender": { "nickname": "UserB" } }]
```

#### 시나리오 2: 알림 차단 테스트
```bash
# 사용자 A: 좋아요 알림 비활성화
PUT /api/users/me/notification-preferences
Authorization: Bearer {user_a_token}
{
  "mode": "both",
  "types": {
    "POST_LIKE": false,  # 좋아요 알림 끄기
    "COMMENT": true
  }
}

# 사용자 B: 다시 좋아요 누르기
POST /api/posts/post123/like
Authorization: Bearer {user_b_token}

# 확인: 사용자 A의 알림 목록 (새 알림 없음)
GET /api/notifications
Authorization: Bearer {user_a_token}
# Response: [] (빈 배열 또는 이전 알림만)
```

---

## 📚 참고 문서

### 관련 파일 위치

| 파일 | 설명 |
|-----|------|
| `app/services/notification_service.py` | 알림 생성 및 FCM 푸시 핵심 로직 |
| `app/models/notification.py` | NotificationType Enum 및 데이터클래스 |
| `app/api/notifications/routes.py` | 알림 조회/확인 API 엔드포인트 |
| `app/api/notifications/config.py` | 메시지 템플릿, 딥링크, 우선순위 설정 |
| `app/api/users/routes.py` | 알림 설정 API (`/me/notification-preferences`) |
| `app/api/users/services/profile_service.py` | 사용자 설정 CRUD 로직 |
| `app/api/comments/services/notification_service.py` | 댓글 도메인 알림 생성 |
| `app/api/posts/services/event_service.py` | 게시글 도메인 알림 생성 |
| `app/api/cartoon_jobs/services/integration_service.py` | 카툰 작업 알림 생성 |

### OpenAPI 문서

```bash
# OpenAPI 스펙 확인
cat openapi_pretty.json | jq '.paths | keys' | grep notification
```

관련 엔드포인트:
- `GET /api/notifications` - 알림 목록 조회
- `POST /api/notifications/{notification_id}/ack` - 알림 확인
- `GET /api/notifications/unread-count` - 미확인 알림 수
- `GET /api/users/me/notification-preferences` - 알림 설정 조회
- `PUT /api/users/me/notification-preferences` - 알림 설정 업데이트
- `PUT /api/users/me/fcm-token` - FCM 토큰 등록

---

## ✅ 체크리스트

### 신규 알림 기능 추가 시
- [ ] `NotificationType` Enum에 타입 추가
- [ ] `NotificationConfig`에 메시지 템플릿 추가
- [ ] Handler 클래스 구현 (선택)
- [ ] 도메인 서비스에서 `create_notification()` 호출
- [ ] 기본 설정에 타입 추가 (`DEFAULT_NOTIFICATION_PREFERENCES`)
- [ ] OpenAPI 문서 재생성 (`swagger_build.py`)
- [ ] 클라이언트 딥링크 처리 구현

### 알림 설정 변경 시
- [ ] 현재 설정 GET으로 먼저 조회
- [ ] 수정 후 전체 `types` 객체를 PUT으로 전송
- [ ] `mode` 필드도 함께 전송 (누락 시 기본값 적용)

---

**작성자**: AI Assistant  
**최종 업데이트**: 2025-10-13  
**버전**: 1.0
