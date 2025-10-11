# API Docstring Style Guide (HappyDog)

## 목표
- 단일 소스(docstring)로 OpenAPI 스펙 생성
- 요약/설명 분리: 첫 줄 = Summary, 공백 줄 이후 = Description (추가 세부사항)
- 오류 기술은 개별 엔드포인트에서 나열하지 않고 error_catalog 중심 관리

## 기본 구조
"""요약 한 줄 (명령형 / 50자 이내)

추가 설명(선택). 비즈니스 규칙, 처리 단계, 부작용.
- 불릿 사용 가능
- 반환 데이터의 의미 강조
"""

## 작성 규칙
1. Summary: 한국어, 동사 시작 (예: "게시글 목록 조회")
2. Description: 선택. 존재 시 Summary와 빈 줄로 분리
3. 금지: HTTP 상태코드/에러코드 직접 나열 (자동 매핑)
4. 스키마 명시: 요청/응답 계약은 Docstring 내 메타 태그로 선언
	- `RequestSchema: <SchemaName>`
	- `ResponseSchema: <SchemaName>` (기본 200)
	- 다중 상태코드: `ResponseSchema[201]: <SchemaName>` / `ResponseSchema[202]: <SchemaName>`
	- 복수 응답 필요 없으면 단일만 작성
5. 가능: 중요한 도메인 제약 (예: "반려동물 최대 5마리")
6. 길이: Summary 50자, Description 단락당 120자 내 권장
7. 선택적 허용: 표준 성공코드(201 Created 등)를 문서화해야 ‘리소스 생성 후 추가 동작(비동기 처리 등)’ 의미 명확성이 필요한 경우에만 `ResponseSchema[201]` 형태로 기술. 일반적인 200 응답은 반복 서술 불필요.

### 메타 태그 파서 동작 개요 (빌더 적용 예정)
- 라우트 docstring에서 줄 단위로 `^RequestSchema:` / `^ResponseSchema(\[\d{3}\])?:` 패턴 추출
- 추출된 스키마명은 `#/components/schemas/<Name>` 으로 매핑
- 명시 없고 POST/PUT/PATCH 인 경우 빌드 로직 경고 (차후 CI fail 전환 가능)
- `RequestSchema:` 는 단일만 허용(향후 multipart/variant 필요 시 확장)

### 네이밍 규칙
- 요청: `*RequestSchema`
- 단건 응답: `*Schema` (도메인 엔티티명 + Schema)
- 리스트/컬렉션: `*ListSchema` (필드 내 items ref)
- 공통 오류: `ErrorResponse` (error_catalog 기반 표준화)

### 빈 바디 및 No Content 정책
- 바디가 없는 POST/PUT/PATCH 라우트라도 반드시 `RequestSchema: EmptyRequestSchema` 명시 (계약 일관성 & 클라이언트 코드 생성 시 분기 제거)
- 204 응답을 의도적으로 반환하는 경우 `ResponseSchema[204]: NoContentSchema` 사용 (본문 없음의 명시적 신호)
- 추후 특정 엔드포인트에서 Relax 필요성이 발견되면 규칙을 예외로 두지 말고 전역 정책을 재논의 (예외 개별 허용 금지)
- 장점: (1) CI에서 단순 규칙 검증 용이 (2) SDK 생성 시 nullable body 처리 분기 최소화 (3) 문서 읽는 사람에게 의도(바디 없음) 즉시 전달

## 예시
### 단일 요청/응답
"""게시글 생성

새로운 게시글을 생성합니다.
- 이미지 파일 경로 배열과 텍스트를 입력받습니다.
- 생성 후 이벤트 서비스가 비동기 후처리를 수행합니다.

RequestSchema: PostCreateRequestSchema
ResponseSchema: PostSchema
"""

### 생성(201)과 비동기 예약(202) 두 응답
"""생성 및 비동기 변환 작업 예약

이미지 업로드 후 변환 파이프라인을 예약합니다.
- 성공 시 즉시 생성된 메타데이터 반환(201)
- 변환 큐 등록만 된 경우 202로 작업 ID 반환

RequestSchema: ImageJobRequestSchema
ResponseSchema[201]: ImageJobCreatedSchema
ResponseSchema[202]: ImageJobQueuedSchema
"""

### 단순 조회(본문 없음)
"""품종 목록 조회

필터 없이 모든 품종을 페이지네이션 없이 반환합니다.

ResponseSchema: BreedListSchema
"""

## 추후 확장 (플레이스홀더)
- @response_schema / @request_schema 데코레이터 제거 후 AST 기반 검사
- :raises: 문법을 활용하여 비즈니스 특수 오류 문서화 (필요 시)
- 페이징, 인증 스니펫 자동 주입
 - Docstring 미지정 스키마 자동 추론(패턴 기반) → 경고 레벨 다운그레이드/업그레이드 정책

## 안티패턴
- "이 엔드포인트는" 으로 시작 (불필요 서술어)
- 과도한 마크다운 표
- 상태코드 중복 설명 (자동화 대상)

## 리뷰 체크리스트
- [ ] Summary 존재 및 명령형
- [ ] Description 핵심 규칙만 기술
- [ ] 에러 나열 금지
- [ ] 비즈니스 제약 누락 없음
- [ ] 불필요한 영문화 지양
 - [ ] 필요한 RequestSchema / ResponseSchema 태그 명시
 - [ ] 다중 응답 필요한 경우만 ResponseSchema[코드] 사용
 - [ ] 스키마 네이밍 규칙 준수 (*RequestSchema / *ListSchema 등)
 - [ ] 201/202 등 특별 상태코드 표기는 의미 차별화 있을 때만
