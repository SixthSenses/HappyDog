# app/api/comments/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.comments.schemas import CommentCreateSchema, CommentResponseSchema


comments_bp = Blueprint('comments_bp', __name__)

@comments_bp.route('/posts/<string:post_id>/comments', methods=['POST'])
@jwt_required()
def create_comment(post_id: str):
    comment_service = current_app.services['comments'] 
    """
    특정 게시글에 새로운 댓글을 작성합니다.
    - 성공 시, 생성된 댓글 정보를 201 Created 상태 코드와 함께 반환합니다.
    - 댓글 생성 후 게시물 작성자 및 멘션된 사용자에게 알림이 생성됩니다.
    """
    user_id = get_jwt_identity()
    try:
        data = CommentCreateSchema().load(request.get_json())
        new_comment = comment_service.create_comment(post_id, user_id, data['text'])
        return jsonify(CommentResponseSchema().dump(new_comment)), 201
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except ValueError as e: # 게시물이 없거나 작성자 정보가 없는 경우
        return jsonify({"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"댓글 생성 중 오류 발생 (post_id: {post_id}): {e}", exc_info=True)
        return jsonify({"error_code": "COMMENT_CREATION_FAILED", "message": "댓글 생성 중 오류가 발생했습니다."}), 500

@comments_bp.route('/posts/<string:post_id>/comments', methods=['GET'])
@jwt_required(optional=True)
def get_comments(post_id: str):
    comment_service = current_app.services['comments'] 
    """
    특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다.
    """
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        comments, next_cursor = comment_service.get_comments_for_post(post_id, user_id, limit, cursor)
        return jsonify({
            "comments": CommentResponseSchema(many=True).dump(comments),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"댓글 목록 조회 중 오류 발생 (post_id: {post_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "댓글 목록 조회 중 오류가 발생했습니다."}), 500


@comments_bp.route('/comments/<string:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id: str):
    comment_service = current_app.services['comments'] 
    """
    특정 댓글을 삭제합니다. (작성자 본인만 가능)
    - 성공 시, 게시물의 댓글 수가 1 감소합니다.
    """
    user_id = get_jwt_identity()
    try:
        comment_service.delete_comment(comment_id, user_id)
        return Response(status=204)
    except PermissionError as e:
        return jsonify({"error_code": "FORBIDDEN", "message": str(e)}), 403
    except ValueError as e:
        return jsonify({"error_code": "NOT_FOUND", "message": str(e)}), 404


@comments_bp.route('/comments/<string:comment_id>/like', methods=['POST'])
@jwt_required()
def toggle_comment_like(comment_id: str):
    comment_service = current_app.services['comments'] 
    """
    특정 댓글의 좋아요를 누르거나 취소합니다.
    """
    user_id = get_jwt_identity()
    try:
        success = comment_service.toggle_comment_like(user_id, comment_id)
        if not success:
            return jsonify({"error_code": "LIKE_TOGGLE_FAILED", "message": "좋아요 처리 중 오류가 발생했습니다."}), 500
        return jsonify({"message": "좋아요 상태가 변경되었습니다."}), 200
    except ValueError as e:
        return jsonify({"error_code": "COMMENT_NOT_FOUND", "message": str(e)}), 404