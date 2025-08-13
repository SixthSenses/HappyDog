# app/api/posts/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.posts.schemas import PostCreateSchema, PostUpdateSchema, PostResponseSchema


posts_bp = Blueprint('posts_bp', __name__)

@posts_bp.route('/', methods=['POST'])
@jwt_required()
def create_post():
    post_service = current_app.services['posts']
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
def get_posts():
    post_service = current_app.services['posts']
    """
    게시글 피드 목록을 페이지네이션으로 조회합니다.
    """
    user_id = get_jwt_identity() # 로그인 시 좋아요 여부 확인, 비로그인 시 None
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        posts, next_cursor = post_service.get_posts(user_id, limit, cursor)
        return jsonify({
            "posts": PostResponseSchema(many=True).dump(posts),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"게시글 목록 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 목록 조회 중 오류가 발생했습니다."}), 500


@posts_bp.route('/<string:post_id>', methods=['GET'])
@jwt_required(optional=True)
def get_post(post_id: str):
    """
    특정 게시글의 상세 정보를 조회합니다.
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    post = post_service.get_post_by_id(post_id, user_id)
    if not post:
        return jsonify({"error_code": "POST_NOT_FOUND", "message": "게시물을 찾을 수 없습니다."}), 404
    return jsonify(PostResponseSchema().dump(post)), 200


@posts_bp.route('/<string:post_id>', methods=['PATCH'])
@jwt_required()
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
def delete_post(post_id: str):
    """
    특정 게시글을 삭제합니다. (작성자 본인만 가능)
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    try:
        post_service.delete_post(post_id, user_id)
        return Response(status=204) # 성공 시 내용 없이 204 No Content 반환
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e: # 게시물이 없는 경우
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404


@posts_bp.route('/<string:post_id>/like', methods=['POST'])
@jwt_required()
def toggle_post_like(post_id: str):
    """
    게시글의 좋아요를 누르거나 취소합니다.
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    try:
        success = post_service.toggle_post_like(user_id, post_id)
        if not success:
            # 서비스 계층에서 False를 반환하는 경우는 일반적인 오류 상황
            return jsonify({"error_code": "LIKE_TOGGLE_FAILED", "message": "좋아요 처리 중 오류가 발생했습니다."}), 500
        return jsonify({"message": "좋아요 상태가 변경되었습니다."}), 200
    except ValueError as e:
        # 서비스 계층에서 게시글을 찾지 못해 발생시킨 예외 처리
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404
    
    
@posts_bp.route('/users/<string:author_id>/posts', methods=['GET'])
@jwt_required(optional=True)
def get_user_posts(author_id: str):
    """
    특정 사용자가 작성한 게시물 피드를 페이지네이션으로 조회합니다.
    (멍스타그램 전용 프로필 화면의 게시물 목록)
    """
    post_service = current_app.services['posts']
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        posts, next_cursor = post_service.get_posts_by_user_id(author_id, user_id, limit, cursor)
        return jsonify({
            "posts": PostResponseSchema(many=True).dump(posts),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"사용자 게시물 목록 조회 중 오류 발생 (author_id: {author_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 목록 조회 중 오류가 발생했습니다."}), 500