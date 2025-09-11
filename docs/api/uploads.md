# uploads API

실제 구현(`app/api/uploads/routes.py`) 및 분리된 스키마 기준. Canonical upload_type 적용 (alias 자동 변환은 일시적).

## 엔드포인트
| Method | Path | Auth | 설명 | 성공 | 주요 오류 |
|---|---|---|---|---|---|
| POST | /api/uploads/url | JWT | 업로드용 Pre-signed URL 발급 | 200 | 400 VALIDATION_ERROR, 401 MISSING_JWT, 500 RECORD_CREATION_FAILED |
| POST | /api/uploads/finalize-cartoon | JWT | 만화 원본 파일 공개 전환 | 200 | 400 VALIDATION_ERROR, 401 MISSING_JWT, 404 NOT_FOUND, 500 UPDATE_FAILED |

## 요청 스키마
UploadUrlRequestSchema:
{
	"upload_type": enum(pet_profile, pet_nose_print, eye_analysis, post_image, cartoon_source_image),
	"filename": string(1..200),
	"content_type": string(3..120)
}

FinalizeCartoonRequestSchema:
{ "file_path": string }

## 응답 예시
/api/uploads/url → 200
{
	"upload_url": "https://storage.googleapis.com/...",
	"file_path": "pet_profiles/user_123/<uuid>.jpg",
	"expires_at": "2025-01-01T12:00:00Z"
}

/api/uploads/finalize-cartoon → 200
{ "public_url": "https://storage.googleapis.com/public/cartoon_123.jpg" }

## 처리 흐름
1) /url 로 사전 서명 URL + 저장될 file_path 획득
2) 클라이언트가 직접 업로드 수행
3) (카툰 변환 등 후속 작업 뒤) /finalize-cartoon 으로 공개 전환
4) 다른 도메인(posts/pets/biometrics)에서 file_path 사용

## 오류 매핑
| 상황 | error_code | 비고 |
|---|---|---|
| 필드 누락/형식 오류 | VALIDATION_ERROR | marshmallow details 포함 |
| 지원 안 되는 upload_type (storage 내부 ValueError) | VALIDATION_ERROR | (에러 카탈로그에 INVALID_UPLOAD_TYPE 없음) |
| URL 생성 중 내부 예외 | RECORD_CREATION_FAILED | 생성 계열 오류 통합 |
| finalize 대상 없는 경우 | NOT_FOUND | FileNotFoundError 매핑 |
| finalize 내부 실패 | UPDATE_FAILED | 일반 수정 실패 통합 |

## 타입 정의
| 타입 | 용도 | 후속 처리 | 공개 전환 필요 |
|------|------|-----------|----------------|
| pet_profile | Pet 프로필 이미지 | Pet 프로필 수정 시 URL 저장 | 필요(현재 bucket 공개 정책에 따라 make_public 호출 가능) |
| pet_nose_print | 비문 분석 원본 | 분석 성공 시 verified 폴더 promote | 일부 (승인 시 promote 후 공개) |
| eye_analysis | 안구 분석 이미지 | 분석 후 결과 저장 | 선택 (결과 응답용 URL 생성 시) |
| post_image | 게시글 이미지 | 게시글 생성 시 참조 | 필요 |
| cartoon_source_image | 만화 변환 원본 | 변환 파이프라인 입력 | finalize 시 공개 |

## Deprecated / Migration
| Deprecated | Canonical 대체 | 비고 |
|-----------|----------------|------|
| profile_image | pet_profile | alias 자동 변환 (유예, 제거 예정) |
| cartoon_source | cartoon_source_image | alias 자동 변환 (유예, 제거 예정) |
| pet_biometric | (제거) | 사용 금지 |
| cartoon_result | (제거) | 서버 생성 산출물, 직접 업로드 불필요 |

## 참고
* upload_type 목록 및 alias 는 `app/api/uploads/schemas.py` 관리
* INVALID_UPLOAD_TYPE / FILE_NOT_FOUND / URL_GENERATION_FAILED 등은 error_catalog 비포함 → 현 단계 VALIDATION_ERROR/NOT_FOUND 사용 (PR4 ErrorUnify 검토 예정)


