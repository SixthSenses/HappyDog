# 🚀 프로젝트 개요 (Project Overview)
- 이 프로젝트는 반려동물의 생체 인식을 기반으로 한 건강 관리 서비스의 백엔드 API입니다.
- 주된 기능은 사용자 관리, 펫 등록 및 생체 정보 처리, 건강 기록 관리 등입니다.

---

## 🛠️ 기술 스택 (Tech Stack)
- **언어**: Python 3.10
- **프레임워크**: Flask
- **데이터베이스**: Google Cloud Firestore (NoSQL)
- **데이터 검증 및 직렬화**: Marshmallow
- **테스트**: Pytest

---

## 🎨 코딩 스타일 및 컨벤션 (Coding Style & Conventions)
- **기본**: PEP 8 스타일 가이드를 철저히 준수합니다.
- **타입 힌팅**: 모든 함수 정의와 변수 선언에 타입 힌팅을 **반드시** 사용해야 합니다.
- **문자열**: 특별한 이유가 없는 한 f-string (`f"Hello, {name}"`)을 사용합니다.
- **언어**: 모든 코드(변수, 함수, 클래스명)와 주석은 **영어**로 작성합니다.

---

## 🏛️ 아키텍처 원칙 (Architectural Principles)
- **구조**: 우리는 **도메인 중심(Domain-First) 구조**를 따릅니다. `user`, `pet` 등 각 도메인 폴더 내에서 `routes`, `services`, `schemas`로 책임을 분리합니다.
- **데이터 모델**: Firestore의 **컬렉션(Collections)과 문서(Documents)** 구조를 사용합니다. 데이터의 구조와 일관성은 Marshmallow 스키마를 통해 애플리케이션 레벨에서 강제합니다.
- **단일 책임 원칙 (SRP)**:
    - `routes.py`: 오직 HTTP 요청을 받고 응답을 반환하는 역할만 합니다. **절대 비즈니스 로직을 포함하지 않습니다.**
    - `services.py`: 실제 비즈니스 로직을 처리합니다.
    - `schemas.py`: Firestore와의 모든 상호작용(CRUD)을 담당합니다. 서비스 계층은 이 모듈을 통해서만 Firestore에 접근해야 합니다.

---

##  E 오류 처리 (Error Handling)
- **중요**: **오류 해결을 위한 임시 코드는 절대 금지합니다. 항상 오류의 근본 원인을 파악하고 해결해주세요.**
- **단일 진실 공급원**: 예측 가능한 모든 비즈니스 오류는 `error_catalog.py`에 정의된 코드를 사용해야 합니다. 임의의 오류 메시지나 코드를 만들지 마세요.
- **예외 처리**: `try-except` 블록에서 `google.cloud.exceptions.NotFound` 와 같은 Firestore 관련 예외나 직접 정의한 비즈니스 예외를 명시적으로 처리하는 것을 권장합니다.

---

## ✅ 테스트 (Testing)
- **프레임워크**: `pytest`를 사용합니다.
- **테스트 환경**: **Firestore Emulator를 사용**하여 테스트를 진행합니다. 실제 운영 데이터베이스에 절대 접근해서는 안 됩니다.
- **패턴**: 모든 테스트는 **Arrange-Act-Assert (AAA)** 패턴을 따라 작성합니다.
- **단위 테스트**: 서비스 계층의 단위 테스트는 Firestore 접근 로직을 Mock 객체로 대체하여 비즈니스 로직에만 집중합니다.
- **통합 테스트**: API 엔드포인트 테스트는 **로컬 Firestore Emulator**를 사용하여 실제와 유사한 환경에서 데이터의 CRUD 동작을 검증합니다.

---

## 💬 커밋 메시지 (Commit Messages)
- **형식**: Conventional Commits 명세를 따릅니다.
  - 예시: `feat: Add user profile update API`
  - 예시: `fix: Correct pagination logic error in pet list`
  - 예시: `refactor: Improve error handling in auth service`

---

## 🔐 보안 (Security)
- **로깅**: 비밀번호, API 키, 개인 식별 정보(PII) 등 민감한 정보는 절대 로그에 남기지 마세요.
- **입력 값 검증**: 클라이언트로부터 들어오는 모든 입력 값은 라우트의 가장 첫 단계에서 **Marshmallow 스키마를 통해 반드시 검증해야 합니다.**
