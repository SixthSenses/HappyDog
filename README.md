## notion 명세서 확인해주세요

## OpenAPI Spec Generation (Unified)

공식 스펙 생성 스크립트는 단일화되었습니다. (레거시 `generate_swagger.py` 제거)

### 기본 생성 (전체 초기화)
```
conda run -n pet-backend python pet_project_backend/scripts/swagger_build.py \
	--app pet_project_backend.app:create_app \
	--out openapi.json --validate
```

### 경량 모드 (문서 전용, 외부 서비스 생략)
Firebase / Storage / ML / OpenAI 초기화를 모두 건너뜁니다.
```
conda run -n pet-backend python pet_project_backend/scripts/swagger_build.py \
	--app pet_project_backend.app:create_app \
	--out openapi.json --validate --docs-mode
```

### 추가 옵션
| 플래그 | 설명 |
|--------|------|
| `--pretty-out FILE` | Pretty JSON 2차 출력 파일 생성 |
| `--minify` | 압축(JSON, 공백 최소화) 출력 |
| `--yaml` | YAML 포맷 출력 |
| `--add-servers` | 서버 리스트 섹션 포함 |
| `--add-tags` | 첫 세그먼트 기반 단순 태그 추론 |
| `--title / --version` | 메타데이터 재정의 |
| `--validate` | prance 기반 OpenAPI 문법 검증 |
| `--docs-mode` | 무거운 외부 초기화 비활성화 |

Docstring 규칙: 첫 줄 Summary, 빈 줄 후 Description. (예: `app/api/.../routes.py` 함수).

에러 응답: `error_catalog` 의 정의가 `components.responses`에 표준화된 형태로 자동 매핑됩니다.

### CI 권장
1. `--docs-mode` 로 스펙 생성 (환경 의존 제거)
2. 생성된 `openapi.json` 을 이전 커밋과 diff → drift 감지 실패 시 PR 실패 처리

### 향후 확장 계획
- Marshmallow 스키마 리플렉션 → components.schemas 자동화
- 인증 스키마(Bearer / Refresh) 추가
- 페이징 공통 meta 구조 자동 삽입
- 커버리지: 실제 라우트 대비 스펙 누락 감지 테스트

이전 `api_documentation` 데코레이터 기반 상세 예제 시스템은 단계적으로 중단되며, 필요 시 추후 메타데이터 병합 유틸 추가 예정입니다.

---

## ML 모델 경로 및 선택적 초기화
비문 / 안구 분석 파이프라인은 선택적(옵셔널) 구성으로, 다른 개발 PC에서 자산이 없어도 서버 기동이 멈추지 않도록 설계되었습니다.

### 환경 변수 (.env)
```
# 상대경로는 pet_project_backend/ 또는 저장소 루트를 기준으로 자동 탐색
YOLO_WEIGHTS_PATH="nose_models/saved_models/nose_segment/best.pt"
EXTRACTOR_WEIGHTS_PATH="nose_models/saved_models/nose_print/seresnext50_ibn_custom_best_model.pth"
FAISS_INDEX_PATH="nose_models/faiss_index/nose_prints.index"
ML_CONFIG_PATH="nose_models/config.yaml"

# ML 파이프라인 완전 비활성 (문서모드/일반 개발 속도 개선)
SKIP_ML=1

# 자산 누락 시 예외를 강제 (CI 무결성 검증 용도)
STRICT_ML_PATHS=1
```

### 초기화 규칙
- `SKIP_ML=1` → nose / eye 모두 미초기화 (`app.services['nose_pipeline'] = None`)
- `STRICT_ML_PATHS=1` & 자산 일부 미존재 → `FileNotFoundError` 로 조기 실패
- 기본 모드에서는 경로가 일부 없으면 경고 출력 후 해당 파이프라인만 skip

### 경로 해석 로직
`app.utils.path_utils.resolve_ml_paths` 가 아래 우선순위로 실제 파일을 탐색:
1. `pet_project_backend/` (백엔드 루트)
2. 저장소 루트

### 로그 예시
```
INFO ML path resolution summary: { 'YOLO_WEIGHTS_PATH': '.../abs/path/best.pt', ... }
WARNING Nose pipeline assets missing or unresolved: ['YOLO_WEIGHTS_PATH', ...] (pipeline skipped)
```

### 팀 온보딩 체크
| 상황 | 권장 설정 |
|------|-----------|
| 모델 필요 없음 / 빠른 API 작업 | `SKIP_ML=1` |
| 모델 기능 개발 | 자산 다운로드 후 상대경로 유지 |
| CI 자산 검증 | `STRICT_ML_PATHS=1` |

### 향후 개선 여지
- Lazy (요청 시) 초기화 전환 옵션
- 모델 버전 메타(`model_manifest.json`) 로 무결성/버전 비교
- 다운로더 스크립트 자동화 (`scripts/download_ml_assets.py` 등)
