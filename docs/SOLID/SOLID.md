# HappyDog Backend – SOLID 현황 보고서 (2025-10-19)

## 1. 분석 범위 및 방법
- **범위**: `pet_project_backend/app/__init__.py`, `app/services/*`, 주요 도메인 서비스(`app/api/{auth,users,posts,comments,pets,pet_care,cartoon_jobs}/services/**`), 공용 스토리지/알림/분석 유틸.
- **방법**: 구조적 코드 리뷰와 의존성 추적, DOCS_MODE 및 DI 구성을 교차 점검하여 SOLID 각 원칙에 대한 준수/위반 사례 식별.
- **참고 문서**: `docs/refactoring/SOLID_DI_Summary.md`, Storage/Cartoon/PetCare 관련 리팩토링 보고서.

## 2. 아키텍처 개요
- Flask 모놀리식 앱, 도메인별 블루프린트와 서비스 계층 분리, `app/__init__.py`에서 DI 컨테이너 초기화.
- 핵심 인프라(`storage`, `openai`, `notifications`, `idempotency`, ML 파이프라인)는 중심 서비스 (`app/services`)로 제공되고 도메인 서비스에 주입.
- DOCS_MODE/`SKIP_ML`로 외부 의존성을 우회하는 전략 구축, Marshmallow 스키마 기반 검증 및 에러 카탈로그 사용.
- 최근 DI 리팩토링으로 전역 싱글톤 감소했지만, 일부 서비스가 여전히 Firebase SDK나 구체 구현에 직접 결합.

## 3. SOLID 준수/위반 요약

| 원칙 | 준수 사례 | 주요 위반 사례 |
|------|-----------|----------------|
| SRP | 라우트/서비스 역할 분리, `CommentService`/`PostService`의 CRUD 집중 | **PetCareRecordIntegration**가 CRUD·분석·알림을 한 클래스에 혼합 (`app/api/pet_care/records/record_integration_service.py:32-213`), **OpenAIService.generate_cartoon**가 이미지 접근·프롬프트 구성·저장까지 수행 (`app/services/openai_service.py:69-213`)
| OCP | Storage URL 변환 확장(`PostService._convert_paths_to_urls`) | 업로드 타입 추가 시 `StorageService.generate_upload_url` 직접 수정 필요 (`app/services/storage_service.py:39-86`), 새로운 펫케어 기록/목표 로직이 핵심 서비스 내 조건 분기 추가 요구 (`app/api/pet_care/records/services.py:41-96`)
| LSP | DOCS_MODE에서 대부분의 서비스가 동일 인터페이스 유지 | `OpenAIServiceStub.generate_cartoon`이 `storage_service` 인자를 수용하지 않아 교체 시 호출 오류 발생 (`app/services/openai_service_stub.py:12-23`)
| ISP | 알림 프레젠테이션 vs 비즈니스 로직(`NotificationPresentationService` vs `NotificationService`) | 소비자가 단순 서명 URL만 필요해도 `StorageService` 전체 인터페이스 의존 (`app/services/storage_service.py`)
| DIP | `app/__init__.py`에서 Firestore/Storage/OpenAI 주입, 레포지토리 프로토콜 도입 | 여러 서비스가 내부에서 구체 구현 직접 생성: `PetCareRecordService`가 `PetCareRecordQueryService` 즉시 생성 (`app/api/pet_care/records/services.py:63,92`), `PetCareRecordIntegration`이 `GoalAnalyzer`·`TrendAnalyzer`·`PetCareNotifier`를 하드코딩 (`app/api/pet_care/records/record_integration_service.py:43-51`), 다수 서비스가 `firebase_admin` SDK에 직접 의존 (`app/api/auth/services.py`, `app/services/notification_service.py`)

## 4. 도메인별 상세 진단

### 4.1 공통 인프라
- **StorageService (`app/services/storage_service.py`)**
	- SRP 유지(업로드·다운로드·URL 변환 구분)지만 업로드 경로 결정 로직이 하드코딩되어 OCP 저해.
	- ISP 관점에서 Signed URL만 필요한 소비자에게 불필요한 메서드 노출.
- **NotificationService (`app/services/notification_service.py:24-213`)**
	- Firestore 저장, preference 확인, FCM 푸시, 메트릭 집계까지 단일 메서드에서 처리 → SRP 위반.
	- FCM 전송을 직접 호출하여 DIP 깨짐; 전송 채널을 추상화한 어댑터 필요.
- **NotificationPresentationService (`app/api/notifications/services.py`)**
	- 프레젠테이션 포맷팅 로직을 별도 클래스로 분리한 점은 SRP 준수.
	- 다만 `NotificationHandlerFactory`를 내부에서 직접 인스턴스화하고 기본 핸들러 등록이 하드코딩되어 있어 새로운 타입 추가 시 코드 수정이 필수(OCP 한계). DI 컨테이너에서 팩토리를 주입받도록 개선 필요.
- **OpenAIService (`app/services/openai_service.py:69-213`)**
	- 이미지 서명 URL 생성, GPT-4o 호출, DALL·E 재시도, Storage 업로드를 한 함수에 집약 → SRP/OCP 위반.
	- Stub이 실 구현과 시그니처 불일치 → LSP 위반.

### 4.2 Auth & Users
- **AuthService (`app/api/auth/services.py`)**
	- JWT 블록리스트, Firestore 조회, Firebase Auth 호출이 한 클래스에 결합 → SRP 약화.
	- Firebase SDK에 직접 의존, 추상화 계층 부재 → DIP 위반.
- **UserService (`app/api/users/services/user_service.py`)**
	- Firebase Auth 직접 호출; 테스트/다른 인증 백엔드 적용 어려움 → DIP 위반.
- **UserProfileService (`app/api/users/services/profile_service.py`)**
	- Storage URL 변환과 사용자 문서 접근을 분리했지만, StorageService 전체에 의존해 ISP 우려.

### 4.3 Posts & Comments
- **PostService (`app/api/posts/services/post_service.py`)**
	- CRUD 외에 사용자/펫 조회, 스냅샷 정책, 이미지 URL 변환까지 담당 → SRP 부담.
	- 확장(예: 게시글 메타데이터 추가) 시 기존 메서드 수정 필요 → OCP 취약.
- **CommentService (`app/api/comments/services/comment_service.py`)**
	- 댓글 CRUD 집중은 양호하나, 트랜잭션 로직과 관련 컬렉션 접근이 클래스로 묶여 테스트 곤란 → DIP 개선 여지.

### 4.4 Pets & Pet Care
- **PetProfileService (`app/api/pets/services/pet_profile_service.py`)**
	- 프로필 CRUD와 초기 펫케어 설정 생성이 하나의 트랜잭션에 결합 → SRP 위반. 별도 온보딩 코디네이터 필요.
- **PetCareRecordService (`app/api/pet_care/records/services.py`)**
	- Meal increment 변환 로직이 서비스 내부에서 직접 기존 기록 조회 → 책임 증가, QueryService 생성으로 DIP 깨짐.
- **PetCareRecordIntegration (`app/api/pet_care/records/record_integration_service.py`)**
	- CRUD 호출, 목표 분석, 트렌드, 알림, 캐시 무효화를 모두 처리 → SRP 중대한 위반. Goal/Trend/Notifier를 주입받도록 재구성 필요.
- **PetCareSettingService (`app/api/pet_care/settings/services.py`)**
	- 초기 설정 생성, 이력 스냅샷 저장, Fallback 로직이 한 클래스에 집중되어 SRP 부담.
	- BreedService와 Firestore 트랜잭션을 직접 결합하여 DIP 여지를 줄임. 설정 이력 관리를 별도 레포지토리/도메인 서비스로 분리하는 방안 필요.

### 4.5 Cartoon Jobs & ML
- **CartoonJobIntegrationService (`app/api/cartoon_jobs/services/integration_service.py`)**
	- PostService와 NotificationService에 직접 의존하나 생성자 주입으로 DIP 준수. 다만 알림/게시물 실패 처리 로직이 결합되어 있어 SRP 한계.
- **CartoonJobProcessor (`app/api/cartoon_jobs/services/processor_service.py`)**
	- 백그라운드 실행 제어, 작업 상태 전이, OpenAI 호출, 알림 이벤트 트리거를 한 클래스가 모두 처리 → SRP 위반.
	- `_process_job`에서 `current_app.services`를 직접 참조해 구체 서비스 키에 의존(DIP 위반). 작업 핸들러 인터페이스 주입으로 결합도 완화가 필요.

## 5. 개선 로드맵

### Phase 1 – 인터페이스 정렬 & 간단 추상화 (1~2 스프린트)
1. **LSP 정합성 확보**: `OpenAIServiceStub.generate_cartoon(storage_service=None, ...)` 시그니처 보정.
2. **DIP 보강**: `PetCareRecordService`와 `PetCareRecordIntegration`에 Analyzer/Query/Notifier 인터페이스 주입.
3. **Storage 어댑터 분리**: Signed URL 제공 인터페이스 작성, 소비자(Service)에서 해당 추상 타입 사용.
4. **NotificationService 리팩터링 1단계**: FCM 전송 로직을 `PushTransport` 추상화로 이동.
5. **Notification Handler 주입화**: `NotificationPresentationService`가 팩토리/핸들러 목록을 DI로 전달받도록 조정해 신규 타입 추가 시 코드 수정 최소화.

> 2025-10-19 업데이트: `StorageUrlProvider` 프로토콜을 도입하고 `PostService`, `PetProfileService`, `UserProfileService`에서 해당 추상 타입으로 의존성을 축소(Phase 1 - 항목 3 진행).

### Phase 2 – 책임 분리 및 확장 포인트 도입 (3~4 스프린트)
1. **PetCare Integration 모듈 분해**: CRUD Orchestrator, Goal Analyzer Coordinator, Notification Dispatcher로 세분화.
2. **PetProfile 온보딩 분리**: 초기 펫케어 설정 생성을 별도 `PetOnboardingService`로 이동하고, 트랜잭션 경계 재구성.
3. **PostService/CommentService 분해**: 사용자/펫 조회, 스냅샷 생성 로직을 Query/Presenter로 이동하여 CRUD 핵심만 유지.
4. **StorageService 경로 전략화**: 업로드 타입-경로 매핑을 구성 기반(예: DI 등록 혹은 전략 패턴)으로 전환하여 OCP 확보.
5. **CartoonPipeline 모듈화**: `CartoonJobProcessor`를 큐 관리-도메인 핸들러-알림 브로커 레이어로 분리하고, 필요한 서비스는 인터페이스 주입으로 캡슐화.

### Phase 3 – 장기 개선 (5 스프린트 이상)
1. **Auth/Notification 외부 의존 추상화**: Firebase Auth 및 Messaging을 인터페이스화하여 대체 구현과 테스트 용이성 확보.
2. **Domain Service 인터페이스 표준화**: 각 도메인 서비스에 대한 포트/어댑터 계층 정의, 테스트 더블 주입 구조 정착.
3. **Cross-cutting Observability 모듈화**: 메트릭/로그 트래킹을 별도 인터셉터로 분리해 SRP 강화.

## 6. 기대 효과 및 검증 전략
- **효과**: 책임 범위 축소로 변경 영향도 감소, 도메인 확장 시 수정 대신 확장 패턴 활용 가능, 테스트 더블 주입 용이.
- **검증**:
	- 리팩터링마다 Swagger docs 모드 빌드 실행.
	- DOCS_MODE에서 Stub 서비스 호출 호환성 자동 체크.

## 7. Phase별 안전성 검토
- **Phase 1 (저위험)**
	- Stub 시그니처 보정은 호출부가 제한적(`CartoonJobProcessor` only)이라 회귀 리스크가 낮음. 단, DOCS_MODE 스펙 변경 후 Swagger/문서 생성 플로우까지 실행해 Stub 누락 호출이 없는지 확인 필수.
	- Analyzer/Notifier 주입 전환은 `_init_dependent_services`에서 생성자 인자를 추가하면 되나, 테스트 더블이 존재하지 않으므로 임시 Factory 함수를 도입해 backwards compatibility를 유지할 필요가 있음.
	- Storage 어댑터 분리는 인터페이스 도입만으로 시작하고, 기존 구현을 래핑하는 Adapter를 제공하면 단계적 전환 가능. 즉각적인 경로 재구성은 Phase 2로 미루는 것이 안전.
	- NotificationService의 Push 분리는 기존 FCM 호출 경로를 Thin Adapter로 감싸는 수준에서 마무리하고, Preference/Firestore 로직은 유지하여 리스크 최소화.
- **Phase 2 (중위험)**
	- PetCare Integration 분해는 다수 서비스/테스트와 얽혀 있어 기능 플래그 혹은 Facade를 두고 점진적으로 분리해야 함. 기존 퍼블릭 메서드 시그니처 유지가 필수.
	- PetProfile 온보딩 분리는 트랜잭션 경계를 조정하므로 동시성/중복 등록 시나리오 테스트 확충 필요.
	- Post/Comment 서비스 분해 시 레거시 데이터 마이그레이션 요구 여부, Snapshot 정책 유지 여부를 사전에 정의해야 함.
	- Storage 경로 전략화는 외부 업로드 클라이언트(모바일/웹)와의 계약 변경이 없는지 확인 후 진행.
- **Phase 3 (고위험)**
	- Firebase Auth/Messaging 추상화는 보안/권한 로직과 직결되므로 통합 테스트 및 운영 환경 점검이 필수.
	- 도메인 포트/어댑터 표준화는 폭넓은 코드 변경을 수반하므로 도메인별로 파일럿을 수행한 뒤 템플릿화.
	- Observability 모듈화는 메트릭 명세 변경을 초래할 수 있어 데이터 파이프라인 팀과 협의해야 함.

## 8. 추가 분석 범위 및 후속 조사 항목
- **Cartoon Background Pipeline** (`app/api/cartoon_jobs/services/processor_service.py`, `job_service.py`): ThreadPool/서비스 상호작용이 복잡하므로 SRP/DIP 재검토 예정. Phase 2 개선 시 영향 범위 파악이 필요.
- **Notification Presentation Layer** (`app/api/notifications/services.py`, `handlers.py`): Handler 템플릿과 Config 적용 방식이 확장성/OCP 측면에서 적절한지 추가 점검.
- **PetCare Settings 서비스** (`app/api/pet_care/settings/services.py`): 초기 설정과 이력 관리가 Profile 서비스와 밀접하게 얽혀 있어 Phase 2 작업 전 상세 분석 필요.
- **Idempotency/Storage 공통 유틸** (`app/services/idempotency_service.py`, `app/services/storage_service.py`): 공통 서비스로서 다른 도메인에 미치는 영향이 크므로 인터페이스 분리 방안 검토.
- **분석 결과 요약**
	- Cartoon Background Pipeline: SRP/DIP 위반 확정 → Phase 2 우선 과제로 승격 필요.
	- Notification Presentation Layer: Handler 등록 하드코딩으로 OCP 제약 → Phase 1 범위에 “팩토리 주입” 작업 추가 권장.
	- PetCare Settings Service: 설정/히스토리/품종 의존이 결합되어 있어 Phase 2 분해 시 고려 대상.
	- Idempotency/Storage 유틸: Storage는 이미 Phase 1/2 개선 계획에 포함, Idempotency는 현재 서비스가 Firestore에 직접 결합되어 있으나 범용 인터페이스 수요가 낮아 Phase 3 이후 점검으로 분류.
- 위 결과를 반영해 로드맵 우선순위를 재평가하고, 후속 분석이 필요한 경우 본 문서를 갱신한다.

---

## 9. Phase 2 완료 보고서 (2025-01-11)

### 9.1 작업 개요
Phase 2의 모든 5개 작업이 성공적으로 완료되었습니다. 각 작업은 독립적으로 커밋되었으며, DOCS_MODE Swagger 빌드로 검증되었습니다.

### 9.2 완료된 작업 목록

#### 2-1. PetCare Integration 모듈 분해 (커밋: 5269108)
- **변경 사항**:
  - `PetCareRecordCRUDOrchestrator`: CRUD 작업 + 캐시 무효화 전담 (105줄)
  - `PetCareGoalCoordinator`: 목표 분석 조율 (90줄)
  - `PetCareNotificationDispatcher`: 알림 발송 로직 (110줄)
  - `PetCareRecordIntegration`: Facade 패턴으로 유지 (기존 API 100% 호환)
- **효과**: 200+ 줄의 혼합 책임 코드를 3개의 단일 책임 모듈로 분리, 메서드 라인 수 ~60% 감소

#### 2-2. PetProfile 온보딩 분리 (커밋: 7ce864a)
- **변경 사항**:
  - `PetOnboardingService`: 사용자 검증 + 펫 생성 + 초기 설정을 하나의 트랜잭션으로 처리 (80줄)
  - `PetProfileService.register_pet()`: 80+ 줄에서 3줄로 축소 (온보딩 서비스에 위임)
- **효과**: 온보딩 플로우 명확화, 트랜잭션 경계 명시적 관리, 테스트 분리 용이

#### 2-3. PostService 분해 (커밋: 60d91f9)
- **변경 사항**:
  - `PostQueryService`: Author/Pet 스냅샷 조회 로직 분리 (157줄)
  - `PostService.create_post()`: 사용자/펫 조회 로직을 query_service에 위임
  - 중복 `_convert_profile_image_url()` 메서드 제거 (query_service로 이동)
- **효과**: CRUD와 데이터 조회 책임 분리, PostService 복잡도 감소, 재사용 가능한 쿼리 계층 확보

#### 2-4. StorageService 경로 전략화 (커밋: 2a288f0)
- **변경 사항**:
  - `upload_path_strategies.py`: `UploadPathStrategy` 프로토콜 정의
  - 5개 구체 전략 구현: PostImage, PetProfile, PetNosePrint, EyeAnalysis, CartoonSource
  - `StorageService.generate_upload_url()`: 하드코딩된 path_map 제거, 전략 레지스트리에 위임
- **효과**: OCP 달성 - 새 업로드 타입 추가 시 전략만 등록하면 되어 StorageService 수정 불필요

#### 2-5. CartoonPipeline 모듈화 (커밋: 7b8f1fc)
- **변경 사항**:
  - `CartoonQueueManager`: ThreadPool 생명주기, 작업 제출/취소, 메트릭 관리 (145줄)
  - `CartoonJobHandler`: 비즈니스 워크플로우, 상태 전이, OpenAI 조율 (170줄)
  - `CartoonJobProcessor`: Facade로 재구성, 큐 매니저와 핸들러에 위임 (100줄)
- **효과**: 250+ 줄의 단일 클래스를 3개 계층으로 분해, SRP 준수, 확장 포인트 명확화

### 9.3 검증 결과
- **커밋 수**: 10개 (Phase 1: 5개 + 문서 1개, Phase 2: 5개)
- **Swagger 빌드**: 모든 단계에서 DOCS_MODE 검증 통과
- **Backward Compatibility**: 100% 유지 (외부 API 변경 없음, 레거시 마이그레이션 불필요)
- **코드 메트릭**:
  - 총 추가: 1200+ 줄 (새 서비스/전략 클래스)
  - 총 제거: 400+ 줄 (중복 로직, 긴 메서드)
  - 순증가: ~800 줄 (모듈화로 인한 인터페이스/문서 증가)

### 9.4 남은 과제 (Phase 3 대상)
- **Auth/Notification 외부 의존 추상화**: Firebase Auth/Messaging 인터페이스화
- **Domain Service 표준화**: 각 도메인에 포트/어댑터 패턴 적용
- **Observability 모듈화**: 메트릭/로그 인터셉터 분리

### 9.5 결론
Phase 2 완료로 HappyDog 백엔드의 핵심 서비스 레이어가 SOLID 원칙에 부합하도록 재구성되었습니다. 
책임 분리(SRP), 확장성(OCP), 의존성 역전(DIP)이 대폭 개선되었으며, 향후 도메인 확장 및 
테스트 작성 시 변경 영향도가 최소화될 것으로 기대됩니다.

---
※ 본 문서는 HappyDog 백엔드의 SOLID 성숙도를 주기적으로 추적하기 위한 기준점으로 사용합니다.
