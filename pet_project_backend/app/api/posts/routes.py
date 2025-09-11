# app/api/posts/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.posts.schemas import PostCreateSchema, PostUpdateSchema, PostResponseSchema
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, PostErrors, RequestExamples, ResponseExamples
)

posts_bp = Blueprint('posts_bp', __name__)

@posts_bp.route('/', methods=['POST'])
@jwt_required()
@api_doc(
    summary="게시글 생성",
    description="새로운 게시글을 생성합니다. 텍스트 내용과 이미지 파일들을 포함할 수 있으며, 생성 후 관련 이벤트가 처리됩니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RESOURCE_NOT_FOUND,
    PostErrors.POST_CREATION_FAILED
)
@request_examples(RequestExamples.CREATE_POST)
@response_examples({
    "name": "post_created",
    "summary": "게시글 생성 성공",
    "description": "새로 생성된 게시글 정보",
    "value": {
        "post_id": "post_123",
        "user_id": "user_456",
        "text": "새로운 게시글 내용입니다.",
        "image_urls": ["https://example.com/image1.jpg"],
        "created_at": "2023-12-10T12:00:00Z",
        "like_count": 0,
        "comment_count": 0,
        "is_liked": False
    }
})
def create_post():
    post_service = current_app.services['posts']
    post_events_service = current_app.services['post_events']
    """
    새로운 게시글을 생성합니다.
    - 요청 본문은 PostCreateSchema에 따라 유효성을 검사합니다.
    - 성공 시, 생성된 게시글 정보를 201 Created 상태 코드와 함께 반환합니다.
    """
    user_id = get_jwt_identity()
    try:
        data = PostCreateSchema().load(request.get_json())
        new_post = post_service.create_post(user_id, data['text'], data['file_paths'])
        if not new_post:
            # 서비스 계층에서 None이 반환된 경우 (예: user/pet 정보 누락)
            raise ValueError("게시글 생성에 필요한 사용자 또는 반려동물 정보를 찾을 수 없습니다.")
        
        # 게시글 생성 이벤트 처리
        post_events_service.handle_post_created(new_post)
        
        return jsonify(PostResponseSchema().dump(new_post)), 201
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except ValueError as e:
        return jsonify({"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"게시글 생성 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "POST_CREATION_FAILED", "message": "게시글 생성 중 오류가 발생했습니다."}), 500

@posts_bp.route('/', methods=['GET'])
@jwt_required(optional=True) # 비로그인 사용자도 피드는 볼 수 있도록 허용
@api_doc(
    summary="게시글 피드 조회",
    description="게시글 피드 목록을 페이지네이션으로 조회합니다. 로그인된 사용자의 경우 좋아요 상태도 함께 반환됩니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples(RequestExamples.PAGINATION_QUERY)
@response_examples(ResponseExamples.PAGINATED_LIST)
def get_posts():
    post_service = current_app.services['posts']
    post_like_service = current_app.services['post_likes']
    """
    게시글 피드 목록을 페이지네이션으로 조회합니다.
    """
    user_id = get_jwt_identity() # 로그인 시 좋아요 여부 확인, 비로그인 시 None
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        posts, next_cursor = post_service.get_posts(limit, cursor)
        
        # 좋아요 정보 추가
        if user_id and posts:
            liked_post_ids = post_like_service.check_likes_for_posts(user_id, [p['post_id'] for p in posts])
            for post in posts:
                post['is_liked'] = post['post_id'] in liked_post_ids
        else:
            for post in posts:
                post['is_liked'] = False
        
        return jsonify({
            "posts": PostResponseSchema(many=True).dump(posts),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"게시글 목록 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 목록 조회 중 오류가 발생했습니다."}), 500


@posts_bp.route('/<string:post_id>', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="특정 게시글 조회",
    description="게시글 ID로 특정 게시글의 상세 정보를 조회합니다. 로그인된 사용자의 경우 좋아요 상태도 함께 반환됩니다.",
    tags=["posts"]
)
@error_responses(
    PostErrors.POST_NOT_FOUND
)
@response_examples({
    "name": "post_detail",
    "summary": "게시글 상세 정보",
    "description": "특정 게시글의 상세 정보",
    "value": {
        "post_id": "post_123",
        "user_id": "user_456",
        "text": "게시글 내용입니다.",
        "image_urls": ["https://example.com/image1.jpg"],
        "created_at": "2023-12-10T12:00:00Z",
        "like_count": 10,
        "comment_count": 5,
        "is_liked": True
    }
})
def get_post(post_id: str):
    """
    특정 게시글의 상세 정보를 조회합니다.
    """
    post_service = current_app.services['posts']
    post_like_service = current_app.services['post_likes']
    user_id = get_jwt_identity()
    
    post = post_service.get_post_by_id(post_id)
    if not post:
        return jsonify({"error_code": "POST_NOT_FOUND", "message": "게시물을 찾을 수 없습니다."}), 404
    
    # 좋아요 정보 추가
    post['is_liked'] = post_like_service.is_user_liked_post(user_id, post_id)
    
    return jsonify(PostResponseSchema().dump(post)), 200


@posts_bp.route('/<string:post_id>', methods=['PATCH'])
@jwt_required()
@api_doc(
    summary="게시글 수정",
    description="특정 게시글의 내용을 수정합니다. 작성자 본인만 수정할 수 있습니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    PostErrors.POST_NOT_OWNED,
    PostErrors.POST_NOT_FOUND,
    PostErrors.POST_UPDATE_FAILED
)
@request_examples(RequestExamples.UPDATE_POST)
@response_examples(ResponseExamples.SUCCESS_UPDATED)
def update_post(post_id: str):
    """
    특정 게시글의 내용을 수정합니다. (작성자 본인만 가능)
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    try:
        data = PostUpdateSchema().load(request.get_json())
        updated_post = post_service.update_post(post_id, user_id, data['text'])
        return jsonify(PostResponseSchema().dump(updated_post)), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e: # 게시물이 없는 경우
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404


@posts_bp.route('/<string:post_id>', methods=['DELETE'])
@jwt_required()
@api_doc(
    summary="게시글 삭제",
    description="특정 게시글을 삭제합니다. 작성자 본인만 삭제할 수 있으며, 관련된 이미지 파일과 이벤트도 함께 처리됩니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    PostErrors.POST_NOT_OWNED,
    PostErrors.POST_NOT_FOUND,
    PostErrors.POST_DELETE_FAILED
)
@response_examples(ResponseExamples.SUCCESS_DELETED)
def delete_post(post_id: str):
    """
    특정 게시글을 삭제합니다. (작성자 본인만 가능)
    """
    post_service = current_app.services['posts']
    post_storage_service = current_app.services['post_storage']
    post_events_service = current_app.services['post_events']
    user_id = get_jwt_identity()
    try:
        # 게시글 삭제 (삭제된 게시글 데이터 반환)
        deleted_post_data = post_service.delete_post(post_id, user_id)
        
        # 스토리지 파일 정리
        image_urls = deleted_post_data.get('image_urls', [])
        if image_urls:
            post_storage_service.cleanup_post_files(image_urls)
        
        # 삭제 이벤트 처리
        post_events_service.handle_post_deleted(deleted_post_data)
        
        return Response(status=204) # 성공 시 내용 없이 204 No Content 반환
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e: # 게시물이 없는 경우
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404


@posts_bp.route('/<string:post_id>/like', methods=['POST'])
@jwt_required()
@api_doc(
    summary="게시글 좋아요 토글",
    description="게시글의 좋아요를 누르거나 취소합니다. 좋아요를 누른 경우에만 게시글 작성자에게 알림이 생성됩니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    PostErrors.POST_NOT_FOUND,
    PostErrors.LIKE_TOGGLE_FAILED
)
@response_examples({
    "name": "post_like_toggled",
    "summary": "좋아요 상태 변경 성공",
    "description": "게시글 좋아요 상태가 성공적으로 변경됨",
    "value": {"message": "좋아요 상태가 변경되었습니다."}
})
def toggle_post_like(post_id: str):
    """
    게시글의 좋아요를 누르거나 취소합니다.
    """
    post_like_service = current_app.services['post_likes']
    post_events_service = current_app.services['post_events']
    user_id = get_jwt_identity()
    try:
        like_event_data = post_like_service.toggle_post_like(user_id, post_id)
        if not like_event_data:
            # 서비스 계층에서 None을 반환하는 경우는 일반적인 오류 상황
            return jsonify({"error_code": "LIKE_TOGGLE_FAILED", "message": "좋아요 처리 중 오류가 발생했습니다."}), 500
        
        # 좋아요 이벤트 처리 (알림 생성)
        if like_event_data.get('action') == 'liked':
            post_events_service.handle_post_liked(like_event_data)
        
        return jsonify({"message": "좋아요 상태가 변경되었습니다."}), 200
    except ValueError as e:
        # 서비스 계층에서 게시글을 찾지 못해 발생시킨 예외 처리
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404
    
    
@posts_bp.route('/users/<string:author_id>/posts', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="사용자별 게시글 조회",
    description="특정 사용자가 작성한 게시물 피드를 페이지네이션으로 조회합니다. 멍스타그램 프로필 화면에서 사용됩니다.",
    tags=["posts"]
)
@error_responses(
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples(RequestExamples.PAGINATION_QUERY)
@response_examples(ResponseExamples.PAGINATED_LIST)
def get_user_posts(author_id: str):
    """
    특정 사용자가 작성한 게시물 피드를 페이지네이션으로 조회합니다.
    (멍스타그램 전용 프로필 화면의 게시물 목록)
    """
    post_service = current_app.services['posts']
    post_like_service = current_app.services['post_likes']
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        posts, next_cursor = post_service.get_posts_by_user_id(author_id, limit, cursor)
        
        # 좋아요 정보 추가
        if user_id and posts:
            liked_post_ids = post_like_service.check_likes_for_posts(user_id, [p['post_id'] for p in posts])
            for post in posts:
                post['is_liked'] = post['post_id'] in liked_post_ids
        else:
            for post in posts:
                post['is_liked'] = False
        
        return jsonify({
            "posts": PostResponseSchema(many=True).dump(posts),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"사용자 게시물 목록 조회 중 오류 발생 (author_id: {author_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 목록 조회 중 오류가 발생했습니다."}), 500