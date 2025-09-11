# app/utils/api_documentation.py
"""
API 문서화를 위한 데코레이터 시스템
각 라우트 함수에 구체적인 오류 시나리오를 선언적으로 정의
"""
import functools
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class CommonErrors(Enum):
    """공통 API 오류 정의"""
    INVALID_JWT = (401, "INVALID_JWT", "The provided JWT is invalid or has expired.")
    MISSING_JWT = (401, "MISSING_JWT", "Authentication token is required.")
    VALIDATION_ERROR = (400, "VALIDATION_ERROR", "Request validation failed.")
    RESOURCE_NOT_FOUND = (404, "NOT_FOUND", "The requested resource could not be found.")
    PERMISSION_DENIED = (403, "PERMISSION_DENIED", "Access to this resource is forbidden.")
    INTERNAL_SERVER_ERROR = (500, "INTERNAL_ERROR", "An unexpected error occurred on the server.")
    RATE_LIMITED = (429, "RATE_LIMITED", "Rate limit exceeded.")


class AuthErrors(Enum):
    """인증 관련 오류 정의"""
    INVALID_SOCIAL_TOKEN = (401, "INVALID_SOCIAL_TOKEN", "Social login token is invalid.")
    UNSUPPORTED_PROVIDER = (400, "UNSUPPORTED_PROVIDER", "Unsupported social login provider.")
    TOKEN_REFRESH_FAILED = (401, "TOKEN_REFRESH_FAILED", "Failed to refresh access token.")
    LOGOUT_FAILED = (400, "LOGOUT_FAILED", "Failed to process logout request.")
    MISSING_CLIENT_SECRETS = (500, "MISSING_CLIENT_SECRETS", "Google client secrets not configured.")


class PetErrors(Enum):
    """반려동물 관련 오류 정의"""
    PET_NOT_FOUND = (404, "PET_NOT_FOUND", "Pet with the specified ID could not be found.")
    PET_NOT_OWNED = (403, "PET_NOT_OWNED", "User does not have permission to access this pet's data.")
    PET_LIMIT_REACHED = (409, "PET_LIMIT_REACHED", "User has reached the maximum number of pets allowed.")
    INVALID_PET_DATA = (400, "INVALID_PET_DATA", "Pet information is invalid or incomplete.")
    BREED_NOT_FOUND = (400, "BREED_NOT_FOUND", "The specified breed does not exist.")
    NOSE_PRINT_DUPLICATE = (409, "NOSE_PRINT_DUPLICATE", "Nose print already exists for another pet.")
    INVALID_IMAGE = (400, "INVALID_IMAGE", "The provided image is invalid or corrupted.")
    ML_SERVICE_ERROR = (500, "ML_SERVICE_ERROR", "Machine learning service encountered an error.")


class PostErrors(Enum):
    """게시글 관련 오류 정의"""
    POST_NOT_FOUND = (404, "POST_NOT_FOUND", "Post with the specified ID could not be found.")
    POST_NOT_OWNED = (403, "POST_NOT_OWNED", "User does not have permission to modify this post.")
    POST_CREATION_FAILED = (500, "POST_CREATION_FAILED", "Failed to create new post.")
    POST_UPDATE_FAILED = (500, "POST_UPDATE_FAILED", "Failed to update post.")
    POST_DELETE_FAILED = (500, "POST_DELETE_FAILED", "Failed to delete post.")
    LIKE_TOGGLE_FAILED = (500, "LIKE_TOGGLE_FAILED", "Failed to toggle post like status.")


class CommentErrors(Enum):
    """댓글 관련 오류 정의"""
    COMMENT_NOT_FOUND = (404, "COMMENT_NOT_FOUND", "Comment with the specified ID could not be found.")
    COMMENT_NOT_OWNED = (403, "COMMENT_NOT_OWNED", "User does not have permission to modify this comment.")
    COMMENT_CREATION_FAILED = (500, "COMMENT_CREATION_FAILED", "Failed to create new comment.")
    COMMENT_DELETE_FAILED = (500, "COMMENT_DELETE_FAILED", "Failed to delete comment.")


class NotificationErrors(Enum):
    """알림 관련 오류 정의"""
    NOTIFICATION_NOT_FOUND = (404, "NOTIFICATION_NOT_FOUND", "Notification could not be found.")
    INVALID_FORMAT = (400, "INVALID_FORMAT", "Unsupported notification format requested.")
    FETCH_FAILED = (500, "FETCH_FAILED", "Failed to fetch notifications.")
    ACK_FAILED = (500, "ACK_FAILED", "Failed to acknowledge notification.")


class PetCareErrors(Enum):
    """펫케어 관련 오류 정의"""
    SETTINGS_NOT_FOUND = (404, "SETTINGS_NOT_FOUND", "Pet care settings not found.")
    UPDATE_FAILED = (500, "UPDATE_FAILED", "Failed to update pet care settings.")
    FUTURE_DATE_NOT_ALLOWED = (400, "FUTURE_DATE_NOT_ALLOWED", "Records cannot be created for future dates.")
    DUPLICATE_RECORD = (409, "DUPLICATE_RECORD", "A record of this type already exists for the specified date.")
    INVALID_RECORD_VALUE = (400, "INVALID_RECORD_VALUE", "Record value is invalid or out of range.")
    RECORD_NOT_FOUND = (404, "RECORD_NOT_FOUND", "Pet care record not found.")
    RECORD_CREATION_FAILED = (500, "RECORD_CREATION_FAILED", "Failed to create pet care record.")
    RECORD_UPDATE_FAILED = (500, "RECORD_UPDATE_FAILED", "Failed to update pet care record.")
    RECORD_DELETION_FAILED = (500, "RECORD_DELETION_FAILED", "Failed to delete pet care record.")
    FETCH_FAILED = (500, "FETCH_FAILED", "Failed to fetch pet care records.")


class CartoonJobErrors(Enum):
    """만화 작업 관련 오류 정의"""
    JOB_CREATION_FAILED = (500, "JOB_CREATION_FAILED", "Failed to create cartoon job.")
    JOB_NOT_FOUND = (404, "JOB_NOT_FOUND_OR_FORBIDDEN", "Job not found or access forbidden.")
    JOB_CANCEL_FAILED = (500, "JOB_CANCEL_FAILED", "Failed to cancel cartoon job.")
    INVALID_STATE_FOR_CANCEL = (409, "INVALID_STATE_FOR_CANCEL", "Job cannot be cancelled in its current state.")
    HEALTH_CHECK_FAILED = (500, "HEALTH_CHECK_FAILED", "Health check failed.")


class BreedErrors(Enum):
    """견종 관련 오류 정의"""
    BREED_NOT_FOUND = (404, "BREED_NOT_FOUND", "Breed with the specified name could not be found.")
    SEARCH_FAILED = (500, "SEARCH_FAILED", "Failed to search breeds.")


class UploadErrors(Enum):
    """업로드 관련 오류 정의"""
    INVALID_PARAMETERS = (400, "INVALID_PARAMETERS", "Missing or invalid upload parameters.")
    INVALID_UPLOAD_TYPE = (400, "INVALID_UPLOAD_TYPE", "Unsupported upload type.")
    URL_GENERATION_FAILED = (500, "URL_GENERATION_FAILED", "Failed to generate upload URL.")
    FILE_NOT_FOUND = (404, "FILE_NOT_FOUND", "File not found in storage.")


class UserErrors(Enum):
    """사용자 관련 오류 정의"""
    USER_NOT_FOUND = (404, "USER_NOT_FOUND", "User with the specified ID could not be found.")
    PROFILE_UPDATE_FAILED = (500, "PROFILE_UPDATE_FAILED", "Failed to update user profile.")
    ACCOUNT_DELETE_FAILED = (500, "ACCOUNT_DELETE_FAILED", "Failed to delete user account.")


class ExternalServiceErrors(Enum):
    """외부 서비스 관련 오류 정의"""
    FIREBASE_CONNECTION_ERROR = (503, "DATABASE_CONNECTION_FAILED", "Database connection failed.")
    ML_SERVICE_UNAVAILABLE = (503, "ML_SERVICE_UNAVAILABLE", "Machine learning service is temporarily unavailable.")
    STORAGE_QUOTA_EXCEEDED = (413, "STORAGE_QUOTA_EXCEEDED", "Storage quota exceeded.")


@dataclass
class ErrorExample:
    """오류 예시 정의"""
    summary: str
    description: str
    error_code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    http_status: int = 400

    @classmethod
    def from_enum(cls, error_enum, details=None):
        """Enum에서 ErrorExample 생성"""
        status, code, description = error_enum.value
        return cls(
            summary=description,
            description=description,
            error_code=code,
            message=description,
            details=details,
            http_status=status
        )


@dataclass
class APIDocumentation:
    """API 문서화 메타데이터"""
    summary: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    error_examples: Dict[int, List[ErrorExample]] = field(default_factory=dict)
    request_examples: List[Dict[str, Any]] = field(default_factory=list)
    response_examples: List[Dict[str, Any]] = field(default_factory=list)



def api_doc(summary: str = "", description: str = "", tags: List[str] = None):
    """API 기본 문서화 데코레이터"""
    def decorator(func):
        if not hasattr(func, '_api_doc'):
            func._api_doc = APIDocumentation()
        
        func._api_doc.summary = summary
        func._api_doc.description = description
        func._api_doc.tags = tags or []
        return func
    return decorator


def error_responses(*error_enums):
    """오류 응답 시나리오 정의 데코레이터 (Enum 기반)"""
    def decorator(func):
        if not hasattr(func, '_api_doc'):
            func._api_doc = APIDocumentation()
        
        for error_enum in error_enums:
            example = ErrorExample.from_enum(error_enum)
            status = example.http_status
            if status not in func._api_doc.error_examples:
                func._api_doc.error_examples[status] = []
            func._api_doc.error_examples[status].append(example)
        
        return func
    return decorator


def request_examples(*examples: Dict[str, Any]):
    """요청 예시 정의 데코레이터"""
    def decorator(func):
        if not hasattr(func, '_api_doc'):
            func._api_doc = APIDocumentation()
        
        func._api_doc.request_examples.extend(examples)
        return func
    return decorator


def response_examples(*examples: Dict[str, Any]):
    """응답 예시 정의 데코레이터"""
    def decorator(func):
        if not hasattr(func, '_api_doc'):
            func._api_doc = APIDocumentation()
        
        func._api_doc.response_examples.extend(examples)
        return func
    return decorator


# 편의성을 위한 헬퍼 함수들
def get_api_doc(func):
    """함수에서 API 문서화 메타데이터 추출"""
    return getattr(func, '_api_doc', None)


def create_swagger_spec_from_docs(app):
    """Flask 앱의 모든 문서화된 엔드포인트에서 Swagger 스펙 생성"""
    # 이 함수는 추후 swagger.json 생성을 위해 사용될 수 있음
    pass


# 공통 응답 예시들
class ResponseExamples:
    """재사용 가능한 응답 예시들"""
    
    SUCCESS_CREATED = {
        "name": "created_success",
        "summary": "성공적인 리소스 생성",
        "description": "새 리소스가 성공적으로 생성됨",
        "value": {"message": "리소스가 성공적으로 생성되었습니다.", "id": "resource_123"}
    }
    
    SUCCESS_UPDATED = {
        "name": "updated_success", 
        "summary": "성공적인 리소스 수정",
        "description": "리소스가 성공적으로 수정됨",
        "value": {"message": "리소스가 성공적으로 수정되었습니다."}
    }
    
    SUCCESS_DELETED = {
        "name": "deleted_success",
        "summary": "성공적인 리소스 삭제", 
        "description": "리소스가 성공적으로 삭제됨",
        "value": {}
    }
    
    PAGINATED_LIST = {
        "name": "paginated_list",
        "summary": "페이지네이션된 목록 응답",
        "description": "커서 기반 페이지네이션을 사용한 목록 조회 결과",
        "value": {
            "items": [],
            "next_cursor": "cursor_123",
            "has_more": True
        }
    }


class RequestExamples:
    """재사용 가능한 요청 예시들"""
    
    PAGINATION_QUERY = {
        "name": "pagination_query",
        "summary": "페이지네이션 쿼리 파라미터",
        "description": "목록 조회 시 사용하는 페이지네이션 파라미터들",
        "value": {"limit": 10, "cursor": "cursor_123"}
    }
    
    CREATE_POST = {
        "name": "create_post",
        "summary": "게시글 생성 요청",
        "description": "새 게시글 생성을 위한 요청 본문",
        "value": {
            "text": "새로운 게시글 내용입니다.",
            "file_paths": ["path/to/image1.jpg", "path/to/image2.jpg"]
        }
    }
    
    UPDATE_POST = {
        "name": "update_post",
        "summary": "게시글 수정 요청", 
        "description": "기존 게시글 수정을 위한 요청 본문",
        "value": {"text": "수정된 게시글 내용입니다."}
    }
    
    CREATE_COMMENT = {
        "name": "create_comment",
        "summary": "댓글 생성 요청",
        "description": "새 댓글 생성을 위한 요청 본문", 
        "value": {"text": "새로운 댓글 내용입니다."}
    }
    
    FCM_TOKEN_REGISTRATION = {
        "name": "fcm_token",
        "summary": "FCM 토큰 등록",
        "description": "푸시 알림을 위한 FCM 토큰 등록 요청",
        "value": {"fcm_token": "fcm_token_string_here"}
    }


# Error examples are now managed through the ErrorCode enum system in error_catalog.py
# This deprecated class has been removed to clean up unused schema definitions
