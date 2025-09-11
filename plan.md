pets 도메인 구조와 핵심 서비스/라우트 코드를 수집해 문제 분석 근거 확보합니다. 레거시 pets/services.py 파일 내용을 확인해 중복/삭제 대상 코드 파악합니다. 요청 수신: 첨부 UI 스크린(마이페이지 / 멍스타그램 / 펫케어 대시보드)와 현재 pets 도메인 전체 코드를 정밀 분석하고, 파일별 처리 전략(경미 수정 / 재작성 / 삭제), 줄 수 근거, 문제 진단 → 리팩토링 계획(1.문제점 2.목표 3.최소 기술 효율적 수정계획) 문서 작성.

## 1. 분석 결과 문서 (파일 상태 & 구조 개선 제안)

### 1.1 UI 스크린에서 추출한 요구(기획 역추적)
| 화면 | 필요한 데이터 그룹 | 관찰 포인트 | 서버 책임 구분 제안 |
|------|------------------|-------------|--------------------|
| 마이페이지 (프로필) | name, breed, age(생일 기반), gender, profile_image, verification badge | 사용자(구글 닉네임 등)는 노출 안됨 | Pet Profile 단순 CRUD (소유자 전용) |
| 멍스타그램(피드) | pet name, breed, age, verified, post_count, profile_image + 게시글 목록 | 타 사용자 pet 접근 허용 유일 뷰 | Social View Projector (가공 전담) |
| 펫케어 대시보드 | 오늘/기간 meal count, activity minutes, weight(별도 domain), stool/vomit, goal 달성률 | pet 문서에 weight 없음 (goal/record domain) | PetCare Aggregator (records + settings) |
| 공통 | 인증 뱃지 is_verified, nose_print_url 필요(내부/표시) | nose_print 등록은 별도 바이오메트릭 | Biometric Service (nose/eye) |

=> 핵심: “다른 사용자에 대한 ‘사용자 프로필’ 접근은 절대 없음” → 현재 라우트에서 `user_id` 파라미터 사용 시 view 검증 로직 강화 필요(있으나 추가 정책 객체화 추천).

### 1.2 Firestore 스키마 (기획 vs 코드 불일치)
기획 스키마:
```
pet: {
  pet_id, user_id, name, gender, breed, birthdate,
  is_verified (bool), profile_image_url?, nose_print_url?,
  faiss_id?, fur_color?, health_concerns: [str]
}
```
코드 현재 Pet dataclass:
```
pet_id, user_id, name, gender(PetGender: MALE/FEMALE), breed,
birthdate, current_weight, is_verified, profile_image_url, nose_print_url,
faiss_id, fur_color, health_concerns, initial_weight (등록 시)
```
불일치/문제:
- current_weight / initial_weight: 기획상 pet 문서에 두지 않고 PetCare 도메인에서 관리해야 함.
- 스키마/예시 혼선: 라우트 예시 JSON은 `gender: "male"` (소문자) / Enum은 "MALE","FEMALE".
- Pet.from_dict 에서 `profile_image_url` 를 pop 제거 → 스펙과 충돌(프론트 필요 필드 유실 위험).
- RegistrationSchema: `birthdate` 필드명 vs route 예시 `birth_date` 혼재.
- Update 예시에 `weight` 등장하지만 Update 스키마에 weight 없음 (죽은 예시, 혼란 가중).

### 1.3 파일별 라인 수 & 처치 분류
| 파일 | 라인 | 분류 | 근거 |
|------|------|------|------|
| routes.py | 382 | 부분 재작성 (핵심 섹션 분리) | 1) View 변환/조립 로직이 라우트에 과다 2) Deprecated endpoint 포함 3) 예시/스키마 불일치 4) 정책/권한 체크 하드코딩 |
| pet_profile_service.py | 360 | 경량 리팩토링 (필드/정책 정리) | CRUD/트랜잭션 핵심 OK. 다만 weight/initial_weight 제거, from_dict/변환 메서드 간소화 필요 |
| pet_biometric_service.py | 337 | 유지 + 일부 추출 | ML 사용 Optional 플래그 좋음. 반환 포맷 통일 + nose/eye 공통 예외 래핑 헬퍼 추출 |
| schemas.py | 83 | 재작성 수준 (짧음) | 필드명/Enum 변환/출력 뷰 분기 명확화 필요. 소문자 ↔ Enum 상호 변환 hook 필요 |
| pet.py | 73 | 부분 수정 | profile_image_url 제거 버그, current_weight 제거, 팩토리 유효성 정리 |
| `services.py` (빈) | 0 | 삭제 (무해) | 잔존 빈 파일 혼동 요소 |
| (간접 영향) __init__.py | - | 소폭 수정 | 서비스 등록 시 presenter/biometric 분리명 명확화 |

삭제 후보 (줄 수 합계):
- Deprecated public profile endpoint (routes.py 약 55~60줄)
- Registration/Update 예시 JSON의 weight 관련 잘못된 부분 (소규모)
- Pet dataclass `current_weight`, `initial_weight` 관련 라인 (약 4~6줄 + 로직 10여줄)
- profile_service 등록/사용 중 weight 초기 설정 로직 (트랜잭션 내 3~4줄)
예상 총 제거 90~110줄.

### 1.4 주요 구조/설계 문제 요약
1. 단일 라우트 파일이 “정책 + 뷰 분기 + 데이터 조합” 모두 수행 (관심사 혼재).
2. View 모델이 암묵적(if view == 'social') 로직 → 프론트 요구 변경 시 다수 분기 증식 위험.
3. Pet 문서 스키마와 PetCare/Weight 경계 모호 (도메인 분리 원칙 위반).
4. Enum/케이스 불일치로 인한 등록 실패 가능성 (실제 입력 'male' vs 기대 'MALE').
5. from_dict 변환 과정에서 필요한 필드 제거(profile_image_url) → 잠재적 UI 결손.
6. 게시글 수(post_count) 집계 책임이 pets 라우트에 존재 (관계된 posts 서비스 이벤트 구조와 어긋남).
7. Nose/Eye ML 실패 시 오류 메시지 형식 비표준 (Error Catalog 미활용).
8. 사용자-펫 연결성 보장: user 문서 `has_pet`, `pet_id` / pet 문서 `user_id` 양방향 있지만 일관성 점검/복구 기능 없음.

### 1.5 리팩토링 난이도 판단
| 주제 | 난이도 | 사유 |
|------|--------|------|
| 스키마/Enum 통일 | 낮음 | Marshmallow pre_load hook |
| weight 필드 제거 | 중간 | 마이그레이션(데이터 존재 시) + 트랜잭션 로직 조정 |
| View Presenter 도입 | 중간 | 간단한 매핑 클래스 + 라우트 정리 |
| Deprecated endpoint 제거 | 낮음 | 클라이언트 공지 필요 여부만 검토 |
| 일관성 점검 스크립트 | 낮음 | Firestore 두 컬렉션 cross-check |
| Biometric 결과 표준화 | 낮음 | 헬퍼 함수/에러 build_error 사용 |
| Post count 조회 위임 | 중간 | UserStatsService / PostEventService 캐시 사용 검토 |
| from_dict 정비 | 낮음 | Model 내부 필드 유지, 변환 안전화 |

### 1.6 권한/정책 적합성 검토
- 현재 `get_pet_profile_by_view` 에서 (target != current && view in ['mypage','petcare']) → 403 반환: 기획 부합.
- 개선: 정책을 상수화 / `PetAccessPolicy.can_view(view, requester, target)` 로 이동해 테스트 용이성 확보.

### 1.7 추가로 발견된 세부 취약/비효율
| 항목 | 설명 | 개선 |
|------|------|------|
| Registration 트랜잭션 중 weight 초기화 | PetCare Domain 초기 설정에 위임 권장 | pet 문서 축소 |
| _pet_to_dict 중복 | Model asdict + 소문자/케이스 처리 가능 | Presenter에서 가공 |
| Gender 변환 Try/Except default MALE | 조용한 오류 → 명시적 ValidationError | 스키마/Enum 매핑 일원화 |
| Nose/Eye 각각 결과 status 포맷 불일치 | success + metadata 혼합 | 표준 `{status, message, data, error_code?}` |
| Profile completion 계산 사용 안됨 | Dead code | 필요 없으면 제거 |
| View별 age_months 계산 로직 라우트 직접 삽입 | 재사용 어려움 | Presenter로 이동 |

---

## 2. 리팩토링 계획 문서

### 2.1 문제점 (정리)
1. 스키마 불일치: 필드명(birthdate vs birth_date), gender 케이스, weight 존재 여부 혼선.
2. 뷰 조합 로직 라우트 과밀(단일 엔드포인트가 3개 뷰 정책 + 데이터 조립).
3. 도메인 경계 훼손: pet 문서가 체중/초기체중 보유(펫케어 책임 중복).
4. 응답 일관성 부족: Nose/Eye 분석, deprecated endpoint, post_count 로직 산재.
5. 모델 변환 오류: profile_image_url 누락(pop), 잠재적 UI 결손.
6. 접근 정책 하드코딩 → 유지보수 취약.
7. 사용자-펫 연결성 무결성 자동 복구/검증 부재.
8. Dead / Deprecated 코드 유지로 인지 부하 증가.
9. 에러 표준 미사용 영역 (ML, 일부 PermissionError 포맷).
10. 테스트 용이성 저하(프리젠테이션/정책/집계 섞임).

### 2.2 목표
1. “단일 진실의 스키마”: 기획 스펙과 코드/문서/예시 동기화.
2. 라우트는 입출력 + 간단한 위임만 담당 (뷰 가공/정책/집계 분리).
3. Pet 문서를 Identity 중심 최소 필드로 정리 (weight 제거).
4. View 별 응답 규격 명확화 (mypage/petcare/social 전용 projector).
5. ML/바이오메트릭 응답/에러 표준화 (Error Catalog 기반).
6. 사용자-펫 연결성 점검/복구 유틸 제공(운영 안전).
7. Deprecated & Dead 코드 제거로 라인 수/인지 부하 감소.
8. Enum/케이스 자동 보정 + Validation 명시화.
9. 후속 확장(추가 view, 추가 지표) 시 OCP 친화적 구조.
10. 최소 변경으로 위험 낮추고 2~3 PR 내 단계적 완료.

### 2.3 최소 기술 · 효율적 수정 계획

#### A. 스키마/모델 정합 (PR 1)
- pet.py:
  - 제거: `current_weight`, `initial_weight`.
  - 유지: `profile_image_url` (pop 제거).
- schemas.py 재작성:
  - Registration: (name, gender, breed, birthdate, fur_color?, health_concerns?, profile_image_url?).
  - pre_load: gender 소문자 → 대문자 변환.
  - 응답 스키마: View별 Schema 분리 (OwnerProfileSchema, SocialProfileSchema, PetcareProfileSchema) 또는 공통 + 선택 필드.
- 마이그레이션 스크립트(간단): 기존 pet 문서에서 weight 관련 필드 제거(존재 시) → PetCare settings 초기 값 반영 여부 확인.

#### B. Presenter & Policy 추출 (PR 2)
- 새 파일: `app/api/pets/presenters.py`
  - `PetViewProjector.build(view, pet, extras)` → dict
  - age_months, post_count(집계 서비스 위임) 계산 분리.
- 새 파일: `app/api/pets/policy.py`
  - `PetAccessPolicy.can_view(view, requester_id, target_user_id)` → bool / error code.
- routes.py 단순화: 분기 삭제, projector 사용, deprecated endpoint 완전 제거.

#### C. Profile Service 정리 (PR 2 같이)
- pet_profile_service.py:
  - weight 관련 로직 삭제 (약 15줄).
  - `_pet_to_dict` 축소 → model asdict + 필요만 가공.
  - profile completion / unused method 제거(원하면 별도 util 이동).

#### D. Biometric 응답 정규화 (PR 3)
- 헬퍼 `build_biometric_response(result: BiometricAnalysisResult)`:
  - 성공: `{status: 'SUCCESS', data: {...}}`
  - 실패: `build_error('ML_SERVICE_ERROR', message=...)`
- Nose/Eye 메서드 내부 try/except 단순화 + 공통 `_safe_download()`.

#### E. Post Count 책임 이동 (PR 3)
- 현재 posts 서비스에 `get_user_post_count` 있음 → UserStatsService / PostEventService 캐시 사용 여부 확인.
- pets routes 에서 posts 직접 접근 제거 → projector에 stats provider 인터페이스 주입.

#### F. 일관성 점검 유틸 (PR 4 - 운영)
- 스크립트: `scripts/verify_pet_link_integrity.py`
  - Scan users where has_pet==True → pet_id 존재 & pet.user_id == user.id
  - 역검증: pets.user_id 가 users에 존재하는지
  - Option `--repair` : 불일치 로그 + 선택적 unset/flag.

#### G. 테스트 추가 (각 PR 마다 최소)
- Enum 케이스 변환 테스트 (male → MALE).
- Policy: 다른 사용자 social 허용 / mypage 금지.
- Presenter: view별 필드 세트 snapshot.
- Biometric 실패/비가용 시 에러 코드 검증.
- Registration 트랜잭션 단일 반려견 정책 재확인.

#### H. 제거/정리 (동행)
| 제거 항목 | 근거 |
|----------|------|
| Deprecated `/pets/<id>/public` | 명시적 문구, 중복 책임 |
| weight 관련 필드/로직 | 도메인 경계 확립 |
| profile completion dead code | 사용처 없음 |
| 빈 `services.py` | 혼동 제거 |
| 잘못된 예시 JSON(weight) | 혼선 제거 |

#### I. 점진적 위험 관리
- PR 순서: Schema/Model → Presenter/Policy & Routes → Biometric 표준화 & PostCount 이동 → Integrity Script.
- 각 단계 후 `/health` + 특정 펫 E2E (등록→조회(social/mypage/petcare)).
- Firestore 변경은 backward compatible: 제거 필드는 무시되므로 위험 낮음.

#### J. 변경 후 기대 효과
| 문제 | 개선 후 |
|------|---------|
| 스키마 혼란 | 단일 소스 정의 & 예시 일치 |
| 라우트 과밀 | 150~180줄 수준 축소 (382→≈190) |
| 도메인 경계 침식 | Pet 문서 = Identity 전용 |
| 권한 하드코딩 | Policy 테스트 가능 |
| 응답 불일관 | 표준화로 프론트 단순화 |
| 운영 무결성 미흡 | 점검 스크립트로 회복 탄력성 |
| ML 에러 난립 | Error catalog 통일 메시지 |

---

### 2.4 예상 라인 변동 (대략)
| 영역 | Before | After 목표 | 변화 |
|------|--------|-----------|------|
| routes.py | 382 | ~190 | -190 |
| pet_profile_service.py | 360 | ~300 | -60 |
| pet_biometric_service.py | 337 | ~310 | -27 |
| schemas.py | 83 | ~95 (뷰 스키마 분리) | +12 |
| pet.py | 73 | ~60 | -13 |
| 신규 presenter/policy | 0 | ~120 | +120 |
| 순감소(총) | - | 약 -160 | 구조 선명화 |

---

## 3. 즉시 실행 가능한 첫 3 Step (착수 제안)
1. PR 1: 모델/스키마 정합 + weight 필드 삭제 + Enum 케이스 hook + Deprecated endpoint 제거.
2. PR 2: Presenter/Policy 도입 → routes 슬림화.
3. PR 3: Biometric 표준 응답 + post_count 책임 이관.

원하시면 바로 PR 1 패치 초안 적용 가능합니다. 다음 단계 진행 여부 알려주세요. 어떤 PR부터 시작할지 혹은 우선순위 조정 필요하면 말씀 주세요.
\n+---\n+\n+## 4. 멍스타그램(Posts / Comments / Cartoon Jobs) 도메인 심층 분석\n+\n+### 4.1 업로드된 멍스타 피드/알림 UI로부터 역추출한 데이터 요구\n+| 화면 요소 | 필요한 데이터 | 현재 제공 여부 | 비고 |\n+|-----------|---------------|----------------|------|\n+| 피드 카드 | post_id, 작성 시각, 이미지 배열(1~N), 본문(text), like_count, comment_count, is_liked, (작성 pet: 이름, 품종, 나이, 프로필 이미지, 인증 뱃지) | 대부분 Post 문서 + 라우트 조합 | age/verified 는 pet 최신값 반영 필요 여부 결정 필요 |\n+| 댓글 토스트/스레드 | comment_id, text, 작성 pet(이름/품종/이미지), like_count, is_liked | 일부 (좋아요 상태 누락) | is_liked 계산 미구현 (아래 버그) |\n+| 알림 목록 | 타입(POST_LIKE, COMMENT, COMMENT_LIKE, MENTION, CARTOON_SUCCESS/FAILED), 보낸 pet/사용자 구분, target_summary (<=80자) | 지원 | 요약 정리 로직 중복 |\n+| 만화 작업 완료 토스트 | job_id -> 결과 이미지 게시글 post_id | 지원 (integration auto post) | 상태/에러 코드 표준화 미흡 |\n+| 4컷 만화형 게시글 | result_image_url 1장 (혹은 추후 다중 지원 여부?) | 지원 | 향후 변형(여러 프레임) 요구 가능성 | \n+\n+핵심 질문(추가 정보 필요):\n+1. 피드에서 pet 이름/프로필 이미지 변경 시 과거 게시글도 실시간 반영 필요? (현재는 생성 시점 pet 스냅샷 → 변경 전파 안 됨)\n+2. 피드에 age(개월) 노출 여부? (UI 캡쳐에는 나이 문구 형태 존재: `4살` 등) → 필요 시 read-time 계산 projector 필요.\n+3. 만화 작업 실패/취소 케이스 알림을 사용자에게 “실패”와 “취소”를 구분해서 보여줄 필요가 있는가?\n+4. 댓글 목록 기본 페이지 크기/최대 허용치? (성능 전략 선택을 위함)\n+5. 좋아요 is_liked 계산은 댓글 목록에서도 반드시 필요? (모바일 UI 계획 확인)\n+\n+### 4.2 현재 구조 요약 vs 이상 구조\n+| 영역 | 현재 | 이상(제안) |\n+|------|------|------------|\n+| Posts | CRUD/Like/Event/Storage 서비스로 분리 (양호) | Feed read 시 Pet 최신 필드 동기화 전략 결정 (lazy projector or denormalize refresh) |\n+| Comments | CRUD / Event / Mention / Notification 서비스로 분리 | Route 버그 수정 + is_liked 일괄 조회 + mention 흐름 정상화 |\n+| Cartoon Jobs | CRUD / Processor / Event / Integration 분리 | 상태 모델 CANCELLED 추가, 에러코드/알림 타입 세분화, 취소 = FAILED 구분 제거 |\n+| 요약 텍스트 sanitize | comment_event_service, comment_notification_service, posts(없음) 각각 중복 | 공용 util (e.g. `app/utils/text_utils.py.truncate_summary`) |\n+| Like 상태 조회 | Posts: bulk in 쿼리, Comments: 미구현 | Comments에 bulk like check 추가 (30개 chunk) |\n+| Pet 데이터 포함 방식 | Post 문서에 pet snapshot 전체 저장 | snapshot + projector 선택 / 또는 pet_id 참조 + read-time join (성능/정합 trade-off 문서화) |\n+\n+### 4.3 치명/주요 논리 버그 (즉시 수정 권장)\n+| 심각도 | 파일/함수 | 문제 | 영향 | 조치 |\n+|--------|-----------|------|------|------|\n+| High | `app/api/comments/routes.py#get_comments` | 호출: `comment_service.get_comments_for_post(post_id, user_id, limit, cursor)` → 서비스 시그니처 `(post_id, limit, cursor)` | `user_id` 문자열이 limit 파라미터로 들어가 Firestore limit 타입 오류/잘못된 결과 | route 에서 user_id 제거 또는 서비스 시그니처 확장 후 내부 처리 |\n+| High | `app/api/comments/routes.py#create_comment` | `comment_events.handle_comment_created(comment_data)` 호출, 실제 정의는 `(comment_data, mention_data)` | 런타임 TypeError → 댓글 생성 시 이벤트 미실행 / 알림/멘션 누락 | route 에서 mention_service 호출 후 두 번째 인자 전달 or 이벤트 서비스가 내부 해석 수행하도록 인터페이스 조정 |\n+| Medium | 댓글 좋아요 is_liked | 댓글 목록 응답 Schema는 is_liked 필드 있지만 설정 로직 없음 | UI is_liked 항상 False | `check_likes_for_comments` 도입 후 list 응답 보강 |\n+| Medium | 중복 `_sanitize_summary` | event_service / notification_service 중복 정의 | 유지보수 비용, 불일치 위험 | util 추출 후 공용 사용, 중복 제거 (약 25~30줄 절감) |\n+| Medium | Cartoon Job 취소 | 취소 → 상태 FAILED로 최종 처리, 알림 타입도 FAILED | 실패와 취소 구분 불가 (UX 혼동) | 상태 ENUM에 CANCELLED 추가, 통합 서비스에서 전용 알림 사용 |\n+| Low | `PostService.create_post` pet snapshot stale | pet 이름/이미지 변경 시 과거 게시글 반영 안 됨 | UX 기대치에 따라 데이터 불일치 | 정책 결정 후 (stale 허용 or lazy refresh endpoint) 구현 |\n+| Low | 에러 코드 불일치 | get_cartoon_job_status: `JOB_NOT_FOUND_OR_FORBIDDEN` 직접 문자열 | 문서 decorator 와 불일치 → API spec 혼란 | ErrorCatalog 코드 사용 + 403/404 분리 |\n+\n+### 4.4 성능/확장 관점 리스크 & 개선 포인트\n+| 항목 | 현 상태 | 리스크 | 개선 |\n+|------|---------|--------|------|\n+| Post feed pet snapshot | write-time denorm | pet 대규모 수정 후 재적재 필요성 | Optional 재동기화 작업/ on-demand projector 캐시 |\n+| 댓글 like 상태 | 미구현 | UX 기능 추가 시 N+1 쿼리 우려 | `check_likes_for_comments` (30개 chunk) 도입 |\n+| Summary truncate | 중복 regex | 느린 건 아니나 drift 위험 | 공용 util + 단위 테스트 |\n+| Cartoon processor 실패 처리 | try/except 중첩, 실패 → 다시 FAILED 업데이트 | 코드 복잡도 | 공통 `_fail_job(job_id, reason)` 헬퍼 추출 |\n+| 멘션 해석 | Firestore where nickname == ... 반복 | 다수 멘션 시 다중 round trip | Nickname→user_id 캐시 (LRU 5~10분) 주입 가능 |\n+| Post count | 이벤트 기반 user_stats 서비스 캐시 | OK | pets projector 시 user_stats 통해 조회 (중복 계산 회피) |\n+\n+### 4.5 삭제/수정 대상 라인 추산 (중복/Dead/Deprecated)\n+| 항목 | 파일 | 추산 라인 | 비고 |\n+|------|------|-----------|------|\n+| 잘못된 get_comments 호출 인자 | comments/routes.py | ~1줄 | 단순 수정 |\n+| handle_comment_created 인자 mismatch | comments/routes.py | ~1줄 + 추가 mention 처리 10~15줄 삽입 | 리팩터 |\n+| Dead `_sanitize_summary` (CommentEventService) | comments/services/event_service.py | ~15줄 | 사용 안 됨 |\n+| 중복 `_sanitize_summary` (NotificationService) | notification_service.py | 유지(기본), 공용 util 로 이동 후 15줄 제거 | 합산 15~30줄 |\n+| Cartoon 취소 FAILED 처리 로직 분기 | cartoon_jobs/services/event_service.py & processor_service.py | ~20줄 조정 | CANCELLED 분리 시 |\n+| 에러 문자열 상수화 | 각 routes | ~10줄 | ErrorCatalog 사용 대체 |\n+| 기타 주석 과다/중복 로깅 | 도메인 전반 | ~30줄 | 선택적 |\n+| 합계(보수적) |  | 약 90~120줄 | 구조 단순화 기대 |\n+\n+### 4.6 제안 API / 구조 개선 요약\n+1. 댓글 라우트 버그 패치 (시급) + mention 흐름 복구.\n+2. `text_utils.truncate_summary(text, max=80)` 유틸 신규 → 댓글 알림/이벤트 양쪽 교체.\n+3. Comments: `get_comments_for_post` 그대로 두고 route 에서 user_id 제거 + 별도 like batch 함수 결과 merge.\n+4. Cartoon Jobs: Status Enum 확장(FAILED, CANCELLED 구분). 취소 이벤트 -> CANCELLED, 알림 타입 CARTOON_CANCELLED 추가.\n+5. Posts: Feed 응답 projector 설계 (pet 최신 정보 포함 옵션 플래그). 기본은 snapshot 유지 → 추가 파라미터 `refresh_pet=true` 시 최신 merge.\n+6. Mentions: mention_service 결과를 이벤트 서비스에 전달 (route 수정) 또는 이벤트 서비스가 self-resolve (단일 책임 명확화 결정 필요).\n+7. Error Catalog 통일: 모든 5xx/4xx에서 `build_error(code, message=...)` 사용.\n+8. 댓글 좋아요 일괄 확인 함수 `check_likes_for_comments` → routes 적용 (이미 서비스에 존재).\n+9. Cartoon Processor 실패 처리 공통 헬퍼 도입 + 로그 레벨 정규화(INFO / WARNING / ERROR 일관성).\n+\n+### 4.7 멍스타그램 전용 리팩토링 단계 (Pet 도메인 PR과 병행 조정)\n+| 단계 | 목표 | 주요 변경 |\n+|------|------|-----------|\n+| M-PR1 (급) | 댓글 라우트/이벤트 치명 버그 수정 | routes 인자 수정, mention resolution 삽입, is_liked 채움 |\n+| M-PR2 | 공용 요약 util + ErrorCatalog 통일 | text util 추가, 중복 제거, 에러코드 정비 |\n+| M-PR3 | Cartoon 상태/알림 개선 | Enum 확장, 취소 처리 분기, 통합 서비스 수정 |\n+| M-PR4 | Feed projector & pet 최신화 전략 | projector 도입, optional refresh 파라미터, 캐시 stub |\n+| M-PR5 (선택) | Mentions 성능 향상 | nickname→user_id LRU 캐시, 통계 util |\n+\n+### 4.8 추가 정보 필요(확정 후 설계 마무리)\n+| 질문 | 설계 영향 |\n+|-------|-----------|\n+| Pet 수정 시 과거 Post 반영 필요 여부? | snapshot vs projector 비용 결정 |\n+| Feed에 age 표기 규칙(년/개월) | projector 계산 포함 여부 |\n+| 댓글 좋아요 is_liked 즉시 필요? | M-PR1 범위/우선순위 |\n+| Cartoon 취소 UI 표현(“취소됨” vs “실패”) | Enum/알림 타입 세분화 가치 |\n+| Mentions 실패(존재X닉네임) 사용자 피드백 방식 | mention_service 반환 구조 UX 반영 |\n+\n+### 4.9 품질 지표 기대 효과\n+| 지표 | 현재 | 개선 후 |\n+|------|------|----------|\n+| 치명 버그(댓글 이벤트) 실패율 | 100% 실패 | 0% (M-PR1) |\n+| 중복/Dead 라인 | ~90–120 | 0 (정리 후) |\n+| 댓글 목록 like 상태 정확성 | 미지원 | 정확한 is_liked 반영 |\n+| Cartoon 취소/실패 구분 | 단일 FAILED | 명확 구분 + 알림 UX 향상 |\n+| Summary truncate 구현 위치 | 2~3곳 중복 | 1 util + 테스트 |\n+\n+### 4.10 다음 즉시 실행안 (제안)\n+1. M-PR1 브랜치 생성 → 댓글 get/list / create 버그 패치 + mention 흐름.\n+2. 간단 단위 테스트: (a) 댓글 생성 시 이벤트 호출 정상, (b) 멘션 2명 포함 시 알림 개수, (c) 댓글 목록 is_liked 반영.\n+3. 완료 후 Pet PR1 병합 타이밍과 충돌 체크 (공용 ErrorCatalog 확장 시 네임 충돌 선점 필요).\n+\n+---\n+\n+위 분석을 기반으로 원하시면 M-PR1 패치 적용을 바로 진행할 수 있습니다. 진행 지시 혹은 추가 확인 사항 알려주세요.\n+