# SOLID DI Refactoring Summary

## 1. 변경 전 (Before)

여러 서비스 클래스가 암묵적으로 Firestore 구현 세부사항에 결합되어 있었습니다. 과거 구조에서는 다음과 같은 문제들이 존재했습니다:
- 일부 서비스가 Firestore 클라이언트를 직접 생성하거나, 간접적으로 전역 접근(숨겨진 싱글톤 패턴)에 의존할 위험
- `DOCS_MODE` 나 환경 분기를 각 서비스별로 중복 판단 → 조건 파편화
- 테스트 시 Firestore 실제 의존성 제거가 어려워 빠른 단위 테스트/시뮬레이션 저해
- 책임 불분명: 서비스가 비즈니스 로직 + 인프라 초기화 논리를 혼재

## 2. 변경 후 (After)

의존 역전 원칙(DIP)을 준수하도록 구조를 재조정했습니다:
- Firestore 초기화는 단일 진입점: `app/core/firestore.py` (`initialize_firestore()`)
- 모든 Firestore 의존 서비스는 `__init__(self, db_client=None)` 패턴으로 주입만 허용
- 서비스 내부에서는 `self.db is None` 여부만으로 동작 경량화(DOCS_MODE 포함) 결정
- 환경 변수 접근(`os.getenv('DOCS_MODE')`)은 앱 팩토리(`create_app`) 단일 위치로 축소
- ML/Storage/OpenAI 등 외부 리소스도 동일한 “존재 여부 기반” 전략으로 정렬

## 3. DI 패턴이 적용된 서비스 목록

아래 서비스들은 모두 Firestore 클라이언트를 외부에서 주입받도록 정규화되었습니다 (필요 없는 서비스는 제외):
- AuthService
- NotificationService
- NotificationPresentationService (간접 Firestore 의존 없음 – 유지)
- CommentService
- CommentMentionService
- CommentNotificationService (Firestore 직접 접근 없음)
- CommentEventService (이벤트 브로커 역할, Firestore 미사용)
- PostService
- PostLikeService
- PostEventService (이벤트 브로커, Firestore 미사용)
- PostStorageService (Storage 의존, Firestore 미사용)
- CartoonJobService
- CartoonJobProcessor (executor 존재 여부로 docs-mode 분기, Firestore 직접 미사용)
- CartoonJobIntegrationService (주입된 post/notification 서비스 존재 여부 기반 경량화)
- CartoonJobEventService (이벤트 브로커)
- PetProfileService
- PetBiometricService
- PetCareSettingService
- PetCareRecordService
- PetCareRecordIntegration (조정자 패턴, 내부 서비스 주입)
- BreedService
- UserProfileService
- UserStatsService
- UserService (경량 – Firestore 직접 사용 없음)
- IdempotencyService
- StorageService (Storage bucket 존재 여부 기반 no-op 모드 지원)
- OpenAIService / OpenAIServiceStub (Firestore 비의존, 동일 초기화 패턴 정렬)
- GoogleAuthService (외부 HTTP 연동, Firestore 비의존 – 그대로 유지)

## 4. 핵심 개선 효과

| 개선 항목 | 설명 |
|-----------|------|
| 결합도 감소 | 서비스가 Firestore 구현 디테일을 모르게 되어 교체/모킹 용이 |
| 테스트 용이성 | `db_client=None` 혹은 Mock 주입으로 단위 테스트 작성 간소화 |
| 단일 책임 | 서비스는 비즈니스 로직만 담당, 인프라 초기화는 팩토리로 이동 |
| 환경 분기 단순화 | DOCS_MODE 분기 로직이 앱 팩토리 한 곳에 집중 (DRY) |
| 예측 가능성 | 의존성 미존재 시 no-op / synthetic 경량 동작으로 문서화/스펙 생성 안정성 확보 |
| 향후 확장성 | 캐시 계층, 다른 DB 어댑터(Firestore→AlloyDB 등) 추가 시 DI 레이어만 확장하면 됨 |

## 5. 패턴 예시 (표준 템플릿)

```python
class ExampleService:
    def __init__(self, db_client=None):
        self.db = db_client
        if self.db is None:
            self.collection = None
            logging.info("ExampleService: No DB client provided, running in no-op mode")
        else:
            self.collection = self.db.collection("example")
```

## 6. 검증 절차
- `grep`으로 `firestore.client(` 호출 위치 검사 → 중앙 초기화 1곳만 남음
- 전역 `os.getenv('DOCS_MODE')` 참조 → `app/__init__.py` 단일 위치
- `swagger_build.py --docs-mode --validate` 실행 → OpenAPI 스펙 성공 생성 (paths/operations 출력 통계)

## 7. 남은/향후 권장 과제
- Marshmallow 스키마 리플렉션 자동 삽입 (components.schemas)
- SecuritySchemes (Bearer / Refresh) 자동 주입 및 각 엔드포인트 보안 요구 분석
- 캐시 레이어(예: Redis) 주입 인터페이스 확장 시 동일 DI 패턴 재사용
- 서비스 계층 위한 통합 Mock/Fixture 헬퍼(`tests/support/factories.py`) 도입
- CartoonJobProcessor executor 자원 해제(shutdown) 훅(app teardown) 추가 고려

## 8. 결론
의존 역전/단일 책임 원칙을 적용하여 서비스 레이어가 ‘상태 + 행위’ 중심의 얇고 예측 가능한 구조로 재정렬되었습니다. 이는 문서 생성(DOCS_MODE), 테스트 속도, 유지보수성을 동시에 개선하며 이후 도메인별 확장(캐시, 메시징, 대체 데이터 소스)에 안정적인 토대를 제공합니다.
