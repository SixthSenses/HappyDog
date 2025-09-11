#!/usr/bin/env python3
"""
Swagger JSON Generator for HappyDog API

이 스크립트는 Flask 앱의 문서화된 엔드포인트들을 스캔하여 OpenAPI 3.0 호환 swagger.json 파일을 생성합니다.
앞서 구축한 api_documentation.py의 데코레이터 시스템을 활용합니다.

사용법:
    python generate_swagger.py
    
출력:
    - swagger.json: OpenAPI 3.0 스펙 파일
    - swagger_pretty.json: 사람이 읽기 쉽게 포맷된 버전
"""

import json
import os
import sys
import inspect
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from flask import Flask

# Flask 앱 경로를 시스템 패스에 추가
sys.path.insert(0, os.path.abspath('.'))

# Flask 앱과 문서화 시스템 임포트
from app import create_app
from app.utils.api_documentation import get_api_doc, ErrorExample


class OpenAPISchemas:
    """OpenAPI 3.0 스키마 정의 관리 클래스"""
    
    @staticmethod
    def get_all_schemas() -> Dict[str, Any]:
        """모든 스키마를 통합하여 반환"""
        schemas = {}
        schemas.update(OpenAPISchemas.get_base_schemas())
        schemas.update(OpenAPISchemas.get_domain_schemas())
        return schemas
    
    @staticmethod
    def get_base_schemas() -> Dict[str, Any]:
        """기본 공통 스키마들을 반환"""
        return {
            "Error": {
                "type": "object",
                "required": ["error_code", "message"],
                "properties": {
                    "error_code": {
                        "type": "string",
                        "description": "에러 코드"
                    },
                    "message": {
                        "type": "string", 
                        "description": "에러 메시지"
                    },
                    "details": {
                        "type": "object",
                        "description": "상세 에러 정보"
                    }
                }
            },
            "PaginationMeta": {
                "type": "object",
                "properties": {
                    "next_cursor": {
                        "type": "string",
                        "nullable": True,
                        "description": "다음 페이지 커서"
                    },
                    "has_more": {
                        "type": "boolean",
                        "description": "더 많은 데이터가 있는지 여부"
                    }
                }
            }
        }
    
    @staticmethod
    def get_domain_schemas() -> Dict[str, Any]:
        """도메인별 스키마들을 반환"""
        return {
            "PetCareRecord": {
                "type": "object",
                "required": ["log_id", "pet_id", "record_type", "timestamp"],
                "properties": {
                    "log_id": {
                        "type": "string",
                        "description": "기록 ID"
                    },
                    "pet_id": {
                        "type": "string",
                        "description": "반려동물 ID"
                    },
                    "record_type": {
                        "type": "string",
                        "enum": ["meal_count", "activity", "weight", "bcs", "stool", "vomit"],
                        "description": "기록 타입"
                    },
                    "timestamp": {
                        "type": "integer",
                        "description": "기록 시간 (Unix timestamp)"
                    },
                    "timestamp_ms": {
                        "type": "integer",
                        "description": "기록 시간 (밀리초)"
                    },
                    "data": {
                        "oneOf": [
                            {"type": "integer"},
                            {"type": "number"},
                            {"type": "string"}
                        ],
                        "description": "기록 데이터 (타입에 따라 다름)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "메모"
                    },
                    "searchDate": {
                        "type": "string",
                        "format": "date",
                        "description": "검색용 날짜 (YYYY-MM-DD)"
                    }
                }
            },
            "UserProfile": {
                "type": "object",
                "required": ["user_id", "nickname"],
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "사용자 ID"
                    },
                    "nickname": {
                        "type": "string",
                        "description": "닉네임"
                    },
                    "profile_image_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "프로필 이미지 URL"
                    },
                    "email": {
                        "type": "string",
                        "format": "email",
                        "description": "이메일"
                    },
                    "bio": {
                        "type": "string",
                        "description": "자기소개"
                    }
                }
            },
            "Pet": {
                "type": "object",
                "required": ["pet_id", "name", "breed_id"],
                "properties": {
                            "pet_id": {
                                "type": "string",
                                "description": "반려동물 ID"
                            },
                            "name": {
                                "type": "string",
                                "description": "반려동물 이름"
                            },
                            "breed_id": {
                                "type": "string",
                                "description": "견종 ID"
                            },
                            "breed_name": {
                                "type": "string",
                                "description": "견종명"
                            },
                            "birth_date": {
                                "type": "string",
                                "format": "date",
                                "description": "생년월일"
                            },
                            "gender": {
                                "type": "string",
                                "enum": ["male", "female"],
                                "description": "성별"
                            },
                            "is_neutered": {
                                "type": "boolean",
                                "description": "중성화 여부"
                            },
                            "profile_image_url": {
                                "type": "string",
                                "format": "uri",
                                "description": "프로필 이미지 URL"
                            }
                        }
                    },
                    "Post": {
                        "type": "object",
                        "required": ["post_id", "user_id", "content"],
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "게시글 ID"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "작성자 ID"
                            },
                            "content": {
                                "type": "string",
                                "description": "게시글 내용"
                            },
                            "image_urls": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                    "format": "uri"
                                },
                                "description": "이미지 URL 목록"
                            },
                            "likes_count": {
                                "type": "integer",
                                "description": "좋아요 수"
                            },
                            "comments_count": {
                                "type": "integer",
                                "description": "댓글 수"
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "생성 시간"
                            }
                        }
                    },
                    "Comment": {
                        "type": "object",
                        "required": ["comment_id", "post_id", "author", "text"],
                        "properties": {
                            "comment_id": {
                                "type": "string",
                                "description": "댓글 ID"
                            },
                            "post_id": {
                                "type": "string",
                                "description": "게시글 ID"
                            },
                            "author": {
                                "type": "object",
                                "required": ["user_id", "nickname"],
                                "properties": {
                                    "user_id": {
                                        "type": "string",
                                        "description": "작성자 ID"
                                    },
                                    "nickname": {
                                        "type": "string",
                                        "description": "작성자 닉네임"
                                    },
                                    "profile_image_url": {
                                        "type": "string",
                                        "format": "uri",
                                        "description": "작성자 프로필 이미지 URL"
                                    }
                                }
                            },
                            "text": {
                                "type": "string",
                                "description": "댓글 내용"
                            },
                            "like_count": {
                                "type": "integer",
                                "description": "좋아요 수"
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "생성 시간"
                            }
                        }
                    },
                    "CartoonJob": {
                        "type": "object",
                        "required": ["job_id", "user_id", "status", "original_image_url"],
                        "properties": {
                            "job_id": {
                                "type": "string",
                                "description": "작업 ID"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "사용자 ID"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["processing", "completed", "failed", "canceling"],
                                "description": "작업 상태"
                            },
                            "original_image_url": {
                                "type": "string",
                                "format": "uri",
                                "description": "원본 이미지 URL"
                            },
                            "result_image_url": {
                                "type": "string",
                                "format": "uri",
                                "description": "결과 이미지 URL"
                            },
                            "user_text": {
                                "type": "string",
                                "description": "사용자 입력 텍스트"
                            },
                            "error_message": {
                                "type": "string",
                                "description": "에러 메시지"
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "생성 시간"
                            },
                            "updated_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "수정 시간"
                            }
                        }
                    },
                    "Notification": {
                        "type": "object",
                        "required": ["notification_id", "recipient_id", "sender", "type", "target_id"],
                        "properties": {
                            "notification_id": {
                                "type": "string",
                                "description": "알림 ID"
                            },
                            "recipient_id": {
                                "type": "string",
                                "description": "알림 수신자 ID"
                            },
                            "sender": {
                                "type": "object",
                                "description": "알림 발송자 정보"
                            },
                            "type": {
                                "type": "string",
                                "enum": ["POST_LIKE", "COMMENT_LIKE", "COMMENT", "MENTION", "CARTOON_SUCCESS", "CARTOON_FAILED", "CARTOON_PROGRESS", "CARTOON_COMPLETED", "PET_CARE_GOAL_REACHED", "PET_CARE_DAILY_SUMMARY"],
                                "description": "알림 타입"
                            },
                            "target_id": {
                                "type": "string",
                                "description": "대상 객체 ID"
                            },
                            "is_read": {
                                "type": "boolean",
                                "description": "읽음 여부"
                            },
                            "created_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "생성 시간"
                            }
                        }
                    },
                    "Breed": {
                        "type": "object",
                        "required": ["breed_id", "name"],
                        "properties": {
                            "breed_id": {
                                "type": "string",
                                "description": "견종 ID"
                            },
                            "name": {
                                "type": "string",
                                "description": "견종명"
                            },
                            "size_category": {
                                "type": "string",
                                "enum": ["small", "medium", "large"],
                                "description": "크기 분류"
                            },
                            "weight_range": {
                                "type": "object",
                                "properties": {
                                    "min": {"type": "number"},
                                    "max": {"type": "number"}
                                },
                                "description": "체중 범위"
                            }
                        }
                    },
                    "PetCareSetting": {
                        "type": "object",
                        "required": ["pet_id", "goals"],
                        "properties": {
                            "pet_id": {
                                "type": "string",
                                "description": "반려동물 ID"
                            },
                            "goals": {
                                "type": "object",
                                "properties": {
                                    "meal_count": {"type": "integer", "description": "목표 식사 횟수"},
                                    "activity": {"type": "integer", "description": "목표 활동량(분)"},
                                    "weight": {"type": "number", "description": "목표 체중"}
                                },
                                "description": "펫케어 목표 설정"
                            },
                            "updated_at": {
                                "type": "string",
                                "format": "date-time",
                                "description": "수정 시간"
                            }
                        }
                    }
                }


class OpenAPIInfo:
    """OpenAPI 기본 정보 및 설정 관리 클래스"""
    
    @staticmethod
    def get_info() -> Dict[str, Any]:
        """API 기본 정보 반환"""
        return {
            "title": "HappyDog API",
            "description": "반려동물 건강 관리 및 소셜 플랫폼 API. Firebase 기반의 백엔드 서비스로, 펫케어 기록, 멍스타그램, 만화 변환 등의 기능을 제공합니다.",
            "version": "1.0.0",
            "contact": {
                "name": "HappyDog Development Team",
                "email": "dev@happydog.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        }
    
    @staticmethod
    def get_servers() -> List[Dict[str, str]]:
        """서버 정보 반환"""
        return [
            {
                "url": "http://localhost:5000/api",
                "description": "개발 서버"
            },
            {
                "url": "https://api.happydog.com/api",
                "description": "프로덕션 서버"
            }
        ]
    
    @staticmethod
    def get_security_schemes() -> Dict[str, Any]:
        """보안 스킴 반환"""
        return {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT 액세스 토큰을 Authorization 헤더에 포함"
            },
            "RefreshTokenAuth": {
                "type": "http", 
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT 리프레시 토큰을 Authorization 헤더에 포함"
            }
        }
    
    @staticmethod
    def get_tags() -> List[Dict[str, str]]:
        """API 태그 반환"""
        return [
            {"name": "auth", "description": "인증 및 로그인 관련 API"},
            {"name": "users", "description": "사용자 프로필 및 계정 관리 API"},
            {"name": "pets", "description": "반려동물 등록 및 프로필 관리 API"},
            {"name": "posts", "description": "멍스타그램 게시글 관리 API"},
            {"name": "comments", "description": "댓글 관리 API"},
            {"name": "pet_care", "description": "펫케어 기록 및 설정 관리 API"},
            {"name": "breeds", "description": "견종 정보 조회 API"},
            {"name": "uploads", "description": "파일 업로드 관리 API"},
            {"name": "notifications", "description": "알림 시스템 API"},
            {"name": "cartoon_jobs", "description": "만화 변환 작업 관리 API"}
        ]


class SwaggerGenerator:
    """OpenAPI 3.0 Swagger JSON 생성기"""
    
    def __init__(self, flask_app: Flask):
        self.app = flask_app
        self.swagger_spec = self._init_base_spec()
    
    def _init_base_spec(self) -> Dict[str, Any]:
        """기본 OpenAPI 스펙 구조 초기화"""
        return {
            "openapi": "3.0.0",
            "info": OpenAPIInfo.get_info(),
            "servers": OpenAPIInfo.get_servers(),
            "paths": {},
            "components": {
                "schemas": OpenAPISchemas.get_all_schemas(),
                "securitySchemes": OpenAPIInfo.get_security_schemes()
            },
            "tags": OpenAPIInfo.get_tags()
        }
        
    def generate(self) -> Dict[str, Any]:
        """Flask 앱을 스캔하여 Swagger 스펙 생성"""
        print("🔍 Flask 앱의 엔드포인트들을 스캔 중...")
        
        with self.app.app_context():
            # 모든 등록된 엔드포인트 스캔
            for rule in self.app.url_map.iter_rules():
                if rule.endpoint == 'static':
                    continue
                    
                # 엔드포인트 함수 가져오기
                try:
                    endpoint_func = self.app.view_functions[rule.endpoint]
                    api_doc = get_api_doc(endpoint_func)
                    
                    if api_doc:  # 문서화된 엔드포인트만 처리
                        self._process_endpoint(rule, endpoint_func, api_doc)
                        print(f"  ✓ {rule.rule} [{', '.join(rule.methods - {'OPTIONS', 'HEAD'})}]")
                    else:
                        print(f"  ⚠️  {rule.rule} - 문서화되지 않은 엔드포인트")
                        
                except Exception as e:
                    print(f"  ❌ {rule.rule} - 처리 중 오류: {e}")
                    continue
        
        print(f"\n📊 총 {len(self.swagger_spec['paths'])} 개의 경로가 문서화되었습니다.")
        return self.swagger_spec
    
    def _process_endpoint(self, rule, endpoint_func, api_doc):
        """개별 엔드포인트 처리"""
        path = self._convert_flask_path_to_openapi(rule.rule)
        
        if path not in self.swagger_spec['paths']:
            self.swagger_spec['paths'][path] = {}
            
        # HTTP 메서드별 처리
        for method in rule.methods:
            if method in ['OPTIONS', 'HEAD']:
                continue
                
            method_lower = method.lower()
            operation = self._build_operation(rule, method, endpoint_func, api_doc)
            self.swagger_spec['paths'][path][method_lower] = operation
    
    def _convert_flask_path_to_openapi(self, flask_path: str) -> str:
        """Flask 경로를 OpenAPI 경로로 변환"""
        # /api 프리픽스 제거 (서버 URL에 이미 포함됨)
        if flask_path.startswith('/api'):
            flask_path = flask_path[4:]
        
        # Flask의 <type:name> 형식을 OpenAPI의 {name} 형식으로 변환
        import re
        return re.sub(r'<(?:string:)?(\w+)>', r'{\1}', flask_path)
    
    def _build_operation(self, rule, method: str, endpoint_func, api_doc) -> Dict[str, Any]:
        """개별 HTTP 오퍼레이션 빌드"""
        operation = {
            "summary": api_doc.summary or f"{method} {rule.rule}",
            "description": api_doc.description or api_doc.summary,
            "tags": api_doc.tags or ["general"],
            "operationId": f"{method.lower()}_{rule.endpoint}",
            "responses": {}
        }
        
        # 파라미터 처리
        parameters = self._extract_parameters(rule)
        if parameters:
            operation["parameters"] = parameters
            
        # 요청 본문 처리
        if method.upper() in ['POST', 'PUT', 'PATCH'] and api_doc.request_examples:
            operation["requestBody"] = self._build_request_body(api_doc.request_examples)
            
        # 응답 처리
        operation["responses"] = self._build_responses(api_doc)
        
        # 보안 요구사항 처리
        security = self._extract_security_requirements(endpoint_func)
        if security:
            operation["security"] = security
            
        return operation
    
    def _extract_parameters(self, rule) -> List[Dict[str, Any]]:
        """URL 경로에서 파라미터 추출"""
        parameters = []
        
        # 경로 파라미터 추출
        for arg in rule.arguments:
            param = {
                "name": arg,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
                "description": f"{arg} 파라미터"
            }
            
            # 타입별 스키마 설정
            if 'id' in arg.lower():
                param["description"] = f"{arg.replace('_', ' ').title()} 식별자"
            elif arg == 'pet_id':
                param["description"] = "반려동물 ID"
            elif arg == 'user_id':
                param["description"] = "사용자 ID"
            elif arg == 'post_id':
                param["description"] = "게시글 ID"
                
            parameters.append(param)
        
        return parameters
    
    def _build_request_body(self, request_examples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """요청 본문 스키마 빌드"""
        if not request_examples:
            return {}
            
        # 첫 번째 예시를 기반으로 스키마 생성
        example = request_examples[0].get("value", {})
        schema = self._get_schema_ref_for_request(example)
        
        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": schema,
                    "examples": {
                        ex.get("name", f"example_{i}"): {
                            "summary": ex.get("summary", ""),
                            "description": ex.get("description", ""),
                            "value": ex.get("value", {})
                        }
                        for i, ex in enumerate(request_examples)
                    }
                }
            }
        }
    
    def _get_schema_ref_for_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """요청 데이터에 따른 적절한 스키마 참조 반환"""
        if not isinstance(request_data, dict):
            return self._infer_schema_from_example(request_data)
        
        # PetCare 기록 생성 요청 감지
        if "record_type" in request_data and "data" in request_data:
            return {
                "type": "object",
                "required": ["record_type", "data"],
                "properties": {
                    "record_type": {
                        "type": "string",
                        "enum": ["meal_count", "activity", "weight", "bcs", "stool", "vomit"],
                        "description": "기록 타입"
                    },
                    "timestamp": {
                        "type": "integer",
                        "description": "기록 시간 (Unix timestamp, 생략시 현재 시간)"
                    },
                    "data": {
                        "oneOf": [
                            {"type": "integer"},
                            {"type": "number"},
                            {"type": "string"}
                        ],
                        "description": "기록 데이터 (타입에 따라 다름)"
                    },
                    "memo": {
                        "type": "string",
                        "description": "메모 (선택사항)"
                    }
                }
            }
        
        # 게시글 생성 요청 감지
        if "content" in request_data and ("image_urls" in request_data or "pet_id" in request_data):
            return {
                "type": "object",
                "required": ["content"],
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "게시글 내용"
                    },
                    "image_urls": {
                        "type": "array",
                        "items": {"type": "string", "format": "uri"},
                        "description": "이미지 URL 목록"
                    },
                    "pet_id": {
                        "type": "string",
                        "description": "반려동물 ID"
                    }
                }
            }
        
        # 댓글 생성 요청 감지
        if "text" in request_data and not "content" in request_data:
            return {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "댓글 내용"
                    }
                }
            }
        
        # 만화 작업 생성 요청 감지
        if "original_image_url" in request_data or "user_text" in request_data:
            return {
                "type": "object",
                "required": ["original_image_url"],
                "properties": {
                    "original_image_url": {
                        "type": "string",
                        "format": "uri",
                        "description": "원본 이미지 URL"
                    },
                    "user_text": {
                        "type": "string",
                        "description": "사용자 입력 텍스트"
                    }
                }
            }
        
        # 펫케어 설정 요청 감지
        if "goals" in request_data:
            return {
                "type": "object",
                "required": ["goals"],
                "properties": {
                    "goals": {
                        "type": "object",
                        "properties": {
                            "meal_count": {"type": "integer", "description": "목표 식사 횟수"},
                            "activity": {"type": "integer", "description": "목표 활동량(분)"},
                            "weight": {"type": "number", "description": "목표 체중"}
                        },
                        "description": "펫케어 목표 설정"
                    }
                }
            }
        
        # 기본적으로 예시에서 스키마 추론
        return self._infer_schema_from_example(request_data)
    
    def _build_responses(self, api_doc) -> Dict[str, Any]:
        """응답 스키마 빌드"""
        responses = {}
        
        # 성공 응답 (200, 201, 204)
        if api_doc.response_examples:
            for example in api_doc.response_examples:
                status_code = "200"  # 기본값
                if "created" in example.get("name", "").lower():
                    status_code = "201"
                elif "deleted" in example.get("name", "").lower():
                    status_code = "204"
                
                if status_code != "204":
                    # 응답 내용에 따라 적절한 스키마 참조 사용
                    schema = self._get_schema_ref_for_response(example.get("value", {}))
                    
                    responses[status_code] = {
                        "description": example.get("summary", "성공"),
                        "content": {
                            "application/json": {
                                "schema": schema,
                                "example": example.get("value", {})
                            }
                        }
                    }
                else:
                    responses[status_code] = {"description": "성공적으로 삭제됨"}
        else:
            responses["200"] = {"description": "성공"}
        
        # 에러 응답
        for status_code, error_examples in api_doc.error_examples.items():
            if error_examples:
                first_error = error_examples[0]
                responses[str(status_code)] = {
                    "description": first_error.summary,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"},
                            "examples": {
                                f"error_{i}": {
                                    "summary": error.summary,
                                    "description": error.description,
                                    "value": {
                                        "error_code": error.error_code,
                                        "message": error.message,
                                        "details": error.details
                                    }
                                }
                                for i, error in enumerate(error_examples)
                            }
                        }
                    }
                }
        
        return responses
    
    def _get_schema_ref_for_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """응답 데이터에 따른 적절한 스키마 참조 반환"""
        if not isinstance(response_data, dict):
            return self._infer_schema_from_example(response_data)
        
        # PetCare 관련 응답 감지
        if "log_id" in response_data and "record_type" in response_data:
            return {"$ref": "#/components/schemas/PetCareRecord"}
        
        # PetCare 설정 응답 감지
        if "goals" in response_data and ("meal_count" in str(response_data) or "activity" in str(response_data)):
            return {"$ref": "#/components/schemas/PetCareSetting"}
        
        # 사용자 프로필 응답 감지
        if "user_id" in response_data and "nickname" in response_data:
            return {"$ref": "#/components/schemas/UserProfile"}
        
        # 반려동물 응답 감지
        if "pet_id" in response_data and "breed_id" in response_data:
            return {"$ref": "#/components/schemas/Pet"}
        
        # 게시글 응답 감지
        if "post_id" in response_data and "content" in response_data:
            return {"$ref": "#/components/schemas/Post"}
        
        # 댓글 응답 감지
        if "comment_id" in response_data and "post_id" in response_data and "author" in response_data:
            return {"$ref": "#/components/schemas/Comment"}
        
        # 만화 작업 응답 감지
        if "job_id" in response_data and "status" in response_data and "original_image_url" in response_data:
            return {"$ref": "#/components/schemas/CartoonJob"}
        
        # 알림 응답 감지
        if "notification_id" in response_data and "recipient_id" in response_data and "type" in response_data:
            return {"$ref": "#/components/schemas/Notification"}
        
        # 견종 응답 감지
        if "breed_id" in response_data and "name" in response_data and "size_category" in response_data:
            return {"$ref": "#/components/schemas/Breed"}
        
        # 목록 응답 감지
        if "items" in response_data and isinstance(response_data["items"], list):
            if response_data["items"]:
                item_schema = self._get_schema_ref_for_response(response_data["items"][0])
            else:
                item_schema = {"type": "object"}
            
            list_schema = {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": item_schema
                    }
                }
            }
            
            # 페이지네이션 정보가 있으면 추가
            if "next_cursor" in response_data or "has_more" in response_data:
                list_schema["properties"]["pagination"] = {"$ref": "#/components/schemas/PaginationMeta"}
            
            return list_schema
        
        # 기본적으로 예시에서 스키마 추론
        return self._infer_schema_from_example(response_data)
    
    def _extract_security_requirements(self, endpoint_func) -> Optional[List[Dict[str, List[str]]]]:
        """함수에서 보안 요구사항 추출"""
        # 소스 코드를 검사해서 @jwt_required 데코레이터 확인
        source = inspect.getsource(endpoint_func)
        
        if '@jwt_required()' in source or '@jwt_required(refresh=True)' in source:
            if 'refresh=True' in source:
                return [{"RefreshTokenAuth": []}]
            else:
                return [{"BearerAuth": []}]
        elif '@jwt_required(optional=True)' in source:
            return []  # 선택적 인증은 보안 요구사항에서 제외
            
        return None
    
    def _infer_schema_from_example(self, example: Any) -> Dict[str, Any]:
        """예시 데이터에서 JSON 스키마 추론"""
        if isinstance(example, dict):
            properties = {}
            required = []
            
            for key, value in example.items():
                properties[key] = self._infer_schema_from_example(value)
                if value is not None and value != "":
                    required.append(key)
                    
            schema = {
                "type": "object",
                "properties": properties
            }
            if required:
                schema["required"] = required
            return schema
        
        elif isinstance(example, list):
            if example:
                return {
                    "type": "array",
                    "items": self._infer_schema_from_example(example[0])
                }
            else:
                return {"type": "array", "items": {}}
        
        elif isinstance(example, str):
            # 날짜/시간 형식 체크
            if any(pattern in example for pattern in ["T", "Z", ":", "-"]) and len(example) > 10:
                return {"type": "string", "format": "date-time"}
            return {"type": "string"}
        
        elif isinstance(example, bool):
            return {"type": "boolean"}
        
        elif isinstance(example, int):
            return {"type": "integer"}
        
        elif isinstance(example, float):
            return {"type": "number"}
        
        else:
            return {"type": "string"}


def main():
    """메인 실행 함수"""
    print("🚀 HappyDog API Swagger 생성기 시작")
    print("=" * 50)
    
    try:
        # Flask 앱 생성 (최소한의 설정으로)
        print("📱 Flask 앱 초기화 중...")
        app = create_app()
        
        # Swagger 생성기 실행
        generator = SwaggerGenerator(app)
        swagger_spec = generator.generate()
        
        # swagger.json 파일로 저장 (압축)
        swagger_path = "swagger.json"
        with open(swagger_path, 'w', encoding='utf-8') as f:
            json.dump(swagger_spec, f, ensure_ascii=False, separators=(',', ':'))
        
        # swagger_pretty.json 파일로 저장 (가독성 좋게)
        swagger_pretty_path = "swagger_pretty.json"
        with open(swagger_pretty_path, 'w', encoding='utf-8') as f:
            json.dump(swagger_spec, f, ensure_ascii=False, indent=2)
        
        print(f"\n✅ Swagger 파일 생성 완료!")
        print(f"   📄 {swagger_path} - 압축된 JSON")
        print(f"   📄 {swagger_pretty_path} - 가독성 좋은 JSON")
        
        # 통계 출력
        paths_count = len(swagger_spec['paths'])
        total_operations = sum(len(methods) for methods in swagger_spec['paths'].values())
        tags_count = len(set(
            tag for path_methods in swagger_spec['paths'].values() 
            for operation in path_methods.values() 
            for tag in operation.get('tags', [])
        ))
        
        print(f"\n📈 생성된 API 문서 통계:")
        print(f"   🛣️  경로 수: {paths_count}")
        print(f"   🔧 총 오퍼레이션 수: {total_operations}")
        print(f"   🏷️  태그 수: {tags_count}")
        
        print(f"\n🌐 Swagger UI에서 확인하려면:")
        print(f"   https://editor.swagger.io/ 에서 {swagger_pretty_path} 파일을 업로드하세요.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
