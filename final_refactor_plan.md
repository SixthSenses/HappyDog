# 최종 수정 계획 (HappyDog Backend)

작성 시점: 데드라인 8시간 남음. 목표: 치명 버그 제거, 스키마/도메인 경계 정리, 최소 범위 리팩토링으로 유지보수성/일관성/테스트 용이성 확보.

---
## 1. 자세한 문제점 (통합)
### 1.1 Pets 도메인
- 스키마 불일치: `birthdate` vs `birth_date`, gender 소문자 입력 vs Enum 대문자, pet 문서에 `current_weight`, `initial_weight` 존재(펫케어 경계 침범).
- View 로직 과밀: `routes.py` 에 정책/뷰/집계(post_count) 혼재 → 382줄 과다.
- Deprecated public profile endpoint 존재.
- `Pet.from_dict` 가 `profile_image_url` pop → 필드 손실 위험.
- 권한 정책 하드코딩(if/else) 테스트 어려움.
- post_count 책임 분산(실제 카운트 이벤트/통계 서비스가 담당해야 함).
- Nose/Eye Biometric 응답/에러 포맷 비표준 (Error Catalog 미사용, 불균일 메시지).
- Dead/미사용 코드 (profile completion 등) 존재.
- 사용자-펫 상호 참조 무결성 자동 점검 부재.

### 1.2 Posts / Comments
- 댓글 라우트 치명 버그 2건:
  1) `get_comments_for_post` 호출 인자 순서/개수 오류 (user_id 잘못 전달 → limit 파라미터 오염).
  2) 이벤트 호출 시 시그니처 불일치 (`handle_comment_created(comment_data)` vs 정의 `(comment_data, mention_data)`).
- 댓글 목록 is_liked 계산 누락 (Schema 필드와 불일치 → UI 기능 제한).
- 요약 텍스트 truncate/sanitize 중복 구현(이벤트/알림 서비스 양쪽).
- Pet snapshot 고정으로 pet 수정 후 feed 반영 정책 미정 (stale 허용 여부 불명확 → 명시 필요).

### 1.3 Cartoon Jobs
- 취소(Cancel)가 FAILED와 동일 처리 → UX/통계 구분 불가.
- 상태 전이/실패 처리 로직 반복 (try/except 후 동일 FAILED 세팅) → 중복/가독성 저하.
- 에러 문자열 하드코딩 (`JOB_NOT_FOUND_OR_FORBIDDEN`).

### 1.4 공통 횡단
- Error Catalog 미활용 구간 다수 (직접 문자열).
- 상수/코드 중복: `_sanitize_summary`, 상태 문자열, route 내 policy 조건.
- 테스트 곤란 구조: 로직이 route 내부 거대 함수에 흡수.
- 폴더 구조 내 역할 모호: presenter/policy/utils 분리 부재.

---
## 2. 목표
1. 치명 댓글 버그 즉시 해소 (기능 정상화 & 알림/멘션 흐름 복원).
2. 스키마/Enum 정합 확보 + Pet 문서 최소화(Identity 중심) → weight 제거.
3. View/정책/집계 분리 (Presenter + Policy) → 라우트 단순화 50% 이상.
4. Like / Mention / Summary 로직 재사용 유틸화 (중복 제거 & 테스트 용이).
5. Cartoon Job 상태 CANCELLED 도입, 실패와 명확 분리.
6. Error Catalog 단일 진입 (문자열 하드코딩 제거, 표준적 응답 포맷).
7. 무결성 검증 스크립트로 user↔pet 링크 점검 (운영 안정성 확보).
8. 최소 PR 수 (4~5개)로 8시간 내 적용 가능하도록 병렬 가능한 부분 분리.
9. Postman 재검증 시나리오 빠른 실행(핵심 happy path + 오류 케이스 1개씩).

---
## 3. PR 병렬/순차 의존성 구분
| PR | 내용 | 병행 가능 여부 | 선행 필요 |
|----|------|----------------|-----------|
| PR1-Critical | 댓글 버그 수정 + 기본 스키마 Enum 케이스 hook + pets weight 제거(모델 경량) | 최우선 (다른 PR과 병행 X) | - |
| PR2-PresenterPolicy | Pets Presenter/Policy + 댓글 is_liked enrich + summary util 추가 | PR1 완료 후 | PR1 |
| PR3-CartoonState | Cartoon CANCELLED 상태 추가 + Error Catalog 적용(해당 도메인) | PR1 후, PR2와 병행 가능 (파일 충돌 적음) | PR1 |
| PR4-ErrorUnify | 전역 Error Catalog 통일(남은 routes) + 중복 sanitize 제거 + comment notification/event 통합 | PR2 이후 권장 (util 의존) | PR2 |
| PR5-Integrity(Optional) | user-pet 무결성 검사/수정 스크립트 | 언제든 (독립) | - |

※ 시간 제약(8h) → 필수: PR1~PR4. PR5는 여유 시.

---
## 4. 최소 기술 · 효율적 수정 계획 (PR별)
### PR1-Critical (예상 1.0~1.5h)
- 수정: `comments/routes.py` 파라미터/이벤트 시그니처.
- 댓글 생성 시 mention_service 호출 후 결과 전달.
- 댓글 목록 응답 기본 구조 유지 (is_liked 는 PR2에서 추가 - 범위 축소로 속도 확보).
- pets: 모델에서 `current_weight`, `initial_weight` 제거 + 스키마 gender 소문자→대문자 변환 hook.
- Deprecated pet public endpoint 제거.
- 테스트(간단): 댓글 생성 200 / 이벤트 오류 없이 통과.

### PR2-PresenterPolicy (예상 1.5~2h)
- `app/api/pets/presenters.py` / `policy.py` 생성.
- Pets routes 분기 제거 → Presenter 사용.
- Post count 조회 posts/user_stats 서비스 위임.
- `app/utils/text_utils.py` 추가 (`truncate_summary`).
- 댓글 목록 is_liked: `check_likes_for_comments` 활용 (30개 chunk) merge.
- 테스트: view별 필드 세트 / is_liked True/False 케이스.

### PR3-CartoonState (예상 1h)
- Enum: CANCELLED 추가.
- cancel 흐름: FAILED 대신 CANCELLED 최종 상태 + 전용 알림 타입.
- `_fail_job()` / `_cancel_job()` 헬퍼로 중복 제거.
- 해당 routes 에 Error Catalog 적용.
- 테스트: create→cancel→status==CANCELLED.

### PR4-ErrorUnify (예상 1.5h)
- 나머지 routes 문자열 에러 → `build_error` 코드 전환.
- `_sanitize_summary` 중복 제거 → text_utils 사용.
- 댓글 이벤트/알림 서비스에서 요약 로직 삭제 후 util 호출.
- 문서 decorators 필요 시 코드명만 변경 (기능 미변경).
- 테스트: 1) 존재하지 않는 post 조회 404 포맷 일치 2) 잘못된 권한 403 포맷 일치.

### PR5-Integrity (Optional 0.5h)
- `scripts/verify_pet_link_integrity.py` 작성 (read-only + optional --repair skeleton).
- 로그 출력 형식 통일.

### 4.1 하드코딩 방지 계획
- Error messages: 전역 `error_catalog` 코드 기반 → 새 코드 필요 시 catalog 추가 후 사용.
- 상태값(Enum): CartoonJobStatus, PetGender 확장/변환 전담 (문자열 직접 비교 금지).
- 상수화: Summary max length (80), chunk size (LIKE_CHECK_BATCH=30) → `app/core/constants.py` 신설 or 기존 config 재활용.
- 라우트 정책 if/else → `PetAccessPolicy` 메서드 캡슐화.
- Magic string 삭제: 알림 타입, job 상태, view 타입 → 전역 enum/Typed constant.

### 4.2 효율적 폴더 구조 개선
신규/변경:
```
app/
  api/
    pets/
      presenters.py
      policy.py
    comments/
      (기존 routes 경량화)
    posts/
      (추후 feed projector 필요 시 presenters.py 확장 가능)
  utils/
    text_utils.py (truncate_summary, maybe normalize_whitespace)
  core/
    constants.py (SUMMARY_MAX_LEN=80, LIKE_BATCH=30)
```
정리:
- 빈 `services.py` 삭제.
- Deprecated pet public endpoint 라우트 제거 후 문서 주석 정리.
- 중복 summary 함수 삭제.

---
## 5. PR별 제거/정리 항목
| PR | 제거/정리 | 라인 절감(추정) |
|----|-----------|----------------|
| PR1 | 댓글 잘못된 호출 2줄, pets weight 로직 10~20줄, deprecated endpoint 55~60줄 | ~70~80 |
| PR2 | pets routes 분기/중복 변환 150~180줄 감소, 중복 post_count 로직 | ~150+ |
| PR3 | Cartoon 중복 실패/취소 처리 20줄 | ~20 |
| PR4 | sanitize 중복 25~30줄, 에러 문자열 10줄, 기타 주석 20줄 | ~55~60 |
| PR5 | 없음(신규 파일) | 0 |
| 합계 |  | 약 295~310 |

---
## 6. 실행 효율(8h 데드라인) 전략
### 6.1 시간 배분(가이드)
| 시간(누적) | 작업 |
|------------|------|
| 0h-1.5h | PR1 구현 + 단위 테스트/로컬 Postman 스모크 |
| 1.5h-3.5h | PR2 구현 (Presenter/Policy + is_liked) |
| 3.5h-4.5h | PR3 (Cartoon 상태/알림) |
| 4.5h-6h | PR4 (Error 통일 + 중복 제거) |
| 6h-7h | 통합 Postman 회귀 테스트 / 문서 업데이트(README/plan) |
| 7h-8h | 최종 보고서 정리 + 예외 남은 부분 점검 |

### 6.2 테스트 최소 세트 (Postman 또는 스크립트)
- 댓글: 생성 → 목록 → is_liked (좋아요 토글 후 재조회) → 삭제.
- Pet: 등록 → social/mypage view 정책 403/200 비교.
- Cartoon: 생성 → 취소 → 상태 CANCELLED.
- Error: 존재하지 않는 post, 접근 불가 comment 각각 404/403 포맷 확인.

### 6.3 위험/완화
| 위험 | 영향 | 완화 |
|------|------|------|
| Pets weight 제거 후 프론트 참조 | 422/필드 누락 | 사전 커뮤니케이션 / 문서에 변경 기록 명시 |
| Presenter 도입 중 필드 누락 | UI 깨짐 | 스냅샷 테스트 / 기존 응답 샘플 비교 |
| CANCELLED 추가로 클라이언트 switch 문 수정 필요 | 알림 표시 오류 | 임시 backward 호환: FAILED 유지 + CANCELLED 병행 1주 알림 (선택) |

### 6.4 보고서 산출물
- 최종: (1) 이 문서 업데이트 (2) 변경된 Error 코드 표 (3) 라인 감소 요약 (4) Postman 테스트 증빙(스크린샷 or 결과 JSON) 첨부.

---
## 7. 바로 다음 액션 제안
1. PR1 브랜치 생성: `refactor/pr1_critical_fixes`.
2. 댓글 routes 수정 + weight 필드 제거 커밋.
3. 간단 유닛/통합 실행 후 PR2 병행 준비.

필요 시 즉시 PR1 패치 적용 진행 지시 주세요.

---
문서 끝.
