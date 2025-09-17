# app/api/posts/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.posts.schemas import (
    PostCreateSchema,
    PostUpdateSchema,
    PostResponseSchema,
    PostsFeedResponseSchema,  # 새 목록/피드 응답 스키마
    PostLikeToggleResponseSchema,
    EmptyRequestSchema,
    NoContentSchema,
)
from app.utils.error_catalog import build_error
from app.utils.api_documentation import CommonErrors
from app.middleware.idempotency_middleware import idempotent_endpoint

posts_bp = Blueprint('posts_bp', __name__)

@posts_bp.route('/', methods=['POST'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('POST',))
def create_post():
    """게시글을 생성합니다.

    클라이언트는 텍스트(`text`)와 업로드 완료된 파일 경로 리스트(`file_paths`)를 전달합니다.
    성공 시 생성된 게시글의 전체 정보를 201 응답으로 반환하며, 생성 이벤트 후속 처리(post_events_service)가 비동기/후속 로직을 트리거합니다.

    RequestSchema: PostCreateSchema
    ResponseSchema[201]: PostResponseSchema
    """
    post_service = current_app.services['posts']
    post_events_service = current_app.services['post_events']
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
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"게시글 생성 중 오류 발생: {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="게시글 생성 중 오류가 발생했습니다.")
        return jsonify(body), status

@posts_bp.route('/', methods=['GET'])
@jwt_required(optional=True)  # 비로그인 사용자도 피드를 볼 수 있도록 허용
def get_posts():
    """게시글 피드 목록을 페이지네이션으로 조회합니다.

    로그인 사용자는 각 게시글의 `is_liked` 상태가 채워집니다.
    커서 기반 페이지네이션(`limit`, `cursor`)을 지원합니다.

    ResponseSchema[200]: PostsFeedResponseSchema
    """
    post_service = current_app.services['posts']
    post_like_service = current_app.services['post_likes']
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
        status, body = build_error('FETCH_FAILED', message="게시물 목록 조회 중 오류가 발생했습니다.")
        return jsonify(body), status


@posts_bp.route('/<string:post_id>', methods=['GET'])
@jwt_required(optional=True)
def get_post(post_id: str):
    """특정 게시글의 상세 정보를 조회합니다.

    로그인 사용자의 경우 해당 게시글 좋아요 여부(`is_liked`)가 포함됩니다.

    ResponseSchema[200]: PostResponseSchema
    """
    post_service = current_app.services['posts']
    post_like_service = current_app.services['post_likes']
    user_id = get_jwt_identity()
    
    post = post_service.get_post_by_id(post_id)
    if not post:
        status, body = build_error('NOT_FOUND', message="게시물을 찾을 수 없습니다.")
        return jsonify(body), status
    
    # 좋아요 정보 추가
    post['is_liked'] = post_like_service.is_user_liked_post(user_id, post_id)
    
    return jsonify(PostResponseSchema().dump(post)), 200


@posts_bp.route('/<string:post_id>', methods=['PATCH'])
@jwt_required()
def update_post(post_id: str):
    """특정 게시글의 내용을 수정합니다. (작성자 본인만 가능)

    RequestSchema: PostUpdateSchema
    ResponseSchema[200]: PostResponseSchema
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    try:
        data = PostUpdateSchema().load(request.get_json())
        updated_post = post_service.update_post(post_id, user_id, data['text'])
        return jsonify(PostResponseSchema().dump(updated_post)), 200
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status
    except PermissionError as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except ValueError as e: # 게시물이 없는 경우
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status


@posts_bp.route('/<string:post_id>', methods=['DELETE'])
@jwt_required()
def delete_post(post_id: str):
    """특정 게시글을 삭제합니다. (작성자 본인만 가능)

    ResponseSchema[204]: NoContentSchema
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
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except ValueError as e: # 게시물이 없는 경우
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status


@posts_bp.route('/<string:post_id>/like', methods=['POST'])
@jwt_required()
def toggle_post_like(post_id: str):
    """게시글의 좋아요를 누르거나 취소합니다.

    RequestSchema: EmptyRequestSchema
    ResponseSchema[200]: PostLikeToggleResponseSchema
    """
    post_like_service = current_app.services['post_likes']
    post_events_service = current_app.services['post_events']
    user_id = get_jwt_identity()
    try:
        like_event_data = post_like_service.toggle_post_like(user_id, post_id)
        if not like_event_data:
            # 서비스 계층에서 None을 반환하는 경우는 일반적인 오류 상황
            status, body = build_error('UPDATE_FAILED', message="좋아요 처리 중 오류가 발생했습니다.")
            return jsonify(body), status
        
        # 좋아요 이벤트 처리 (알림 생성)
        if like_event_data.get('action') == 'liked':
            post_events_service.handle_post_liked(like_event_data)
        
        return jsonify({"message": "좋아요 상태가 변경되었습니다."}), 200
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    
    
@posts_bp.route('/users/<string:author_id>/posts', methods=['GET'])
@jwt_required(optional=True)
def get_user_posts(author_id: str):
    """특정 사용자가 작성한 게시물 피드를 페이지네이션으로 조회합니다.

    멍스타그램 프로필 전용 엔드포인트이며 구조는 일반 피드와 동일합니다.

    ResponseSchema[200]: PostsFeedResponseSchema
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
        status, body = build_error('FETCH_FAILED', message="게시물 목록 조회 중 오류가 발생했습니다.")
        return jsonify(body), status