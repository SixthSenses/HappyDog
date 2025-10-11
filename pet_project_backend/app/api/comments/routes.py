# app/api/comments/routes.py
import logging
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.comments.schemas import (
    CommentCreateSchema,
    CommentResponseSchema,
    CommentListResponseSchema,
    CommentLikeToggleResponseSchema,
)
from app.utils.error_catalog import build_error
from app.middleware.idempotency_middleware import idempotent_endpoint

comments_bp = Blueprint('comments_bp', __name__)

@comments_bp.route('/posts/<string:post_id>/comments', methods=['POST'])
@jwt_required()
@idempotent_endpoint(apply_when_methods=('POST',))
def create_comment(post_id: str):
    """댓글 생성

    특정 게시글에 새로운 댓글을 작성합니다. 댓글 생성 후 게시물 작성자 및 멘션된 사용자에게 알림이 생성됩니다.

    RequestSchema: CommentCreateSchema
    ResponseSchema[201]: CommentResponseSchema
    """
    comment_service = current_app.services['comments']
    comment_events = current_app.services['comment_events']
    mention_service = current_app.services.get('comment_mentions')

    user_id = get_jwt_identity()
    try:
        data = CommentCreateSchema().load(request.get_json())
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status

    text = data['text']
    try:
        comment_data = comment_service.create_comment(post_id, user_id, text)
        mention_data = {'mentioned_user_ids': []}
        if mention_service:
            try:
                mention_data = mention_service.resolve_mentions_from_text(text, user_id)
            except Exception as me:
                logging.warning(f"멘션 해석 실패(무시): {me}")
        comment_events.handle_comment_created(comment_data, mention_data)
        return jsonify(CommentResponseSchema().dump(comment_data)), 201
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"댓글 생성 중 오류 발생 (post_id: {post_id}): {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="댓글 생성 중 오류가 발생했습니다.")
        return jsonify(body), status


@comments_bp.route('/posts/<string:post_id>/comments', methods=['GET'])
@jwt_required(optional=True)
def get_comments(post_id: str):
    """댓글 목록 조회

    특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다. 로그인 사용자의 경우 좋아요 상태도 함께 반환됩니다.

    ResponseSchema[200]: CommentListResponseSchema
    """
    comment_service = current_app.services['comments']
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        comments, next_cursor = comment_service.get_comments_for_post(post_id, limit, cursor)
        if user_id:
            try:
                comment_ids = [c.get('comment_id') for c in comments]
                liked_ids = comment_service.check_likes_for_comments(user_id, comment_ids)
                for c in comments:
                    c['is_liked'] = c.get('comment_id') in liked_ids
            except Exception as like_err:
                logging.warning(f"Failed to enrich comments with like info: {like_err}")
        return jsonify({
            "comments": CommentResponseSchema(many=True).dump(comments),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"댓글 목록 조회 중 오류 발생 (post_id: {post_id}): {e}", exc_info=True)
        status, body = build_error('FETCH_FAILED', message="댓글 목록 조회 중 오류가 발생했습니다.")
        return jsonify(body), status


@comments_bp.route('/comments/<string:comment_id>', methods=['DELETE'])
@jwt_required()
def delete_comment(comment_id: str):
    """댓글 삭제

    특정 댓글을 삭제합니다. (작성자 본인만 가능) 성공 시 204 No Content.

    ResponseSchema[204]: NoContentSchema
    """
    comment_service = current_app.services['comments']
    user_id = get_jwt_identity()
    try:
        comment_service.delete_comment(comment_id, user_id)
        return Response(status=204)
    except PermissionError as e:
        status, body = build_error('FORBIDDEN', message=str(e))
        return jsonify(body), status
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status


@comments_bp.route('/comments/<string:comment_id>/like', methods=['POST'])
@jwt_required()
def toggle_comment_like(comment_id: str):
    """댓글 좋아요 토글

    특정 댓글의 좋아요를 누르거나 취소합니다.

    RequestSchema: EmptyRequestSchema
    ResponseSchema[200]: CommentLikeToggleResponseSchema
    """
    comment_service = current_app.services['comments']
    comment_events = current_app.services['comment_events']
    user_id = get_jwt_identity()
    try:
        like_data = comment_service.toggle_comment_like(user_id, comment_id)
        if not like_data:
            raise Exception("LIKE_TOGGLE_INTERNAL_ERROR")
        liked_now = (like_data.get('action') == 'liked')
        if liked_now:
            comment_events.handle_comment_liked(like_data)
        return jsonify(CommentLikeToggleResponseSchema().dump({
            "message": "좋아요 상태가 변경되었습니다.",
            "liked": liked_now,
            "comment_id": comment_id
        })), 200
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"댓글 좋아요 처리 중 오류 발생 (comment_id: {comment_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="좋아요 처리 중 오류가 발생했습니다.")
        return jsonify(body), status