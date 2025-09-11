# app/api/comments/routes.py
import logging
from flask import Blueprint, request, jsonify, Response, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.comments.schemas import CommentCreateSchema, CommentResponseSchema
from app.utils.error_catalog import build_error
from app.utils.api_documentation import (
    api_doc, error_responses, request_examples, response_examples,
    CommonErrors, CommentErrors, RequestExamples, ResponseExamples
)

comments_bp = Blueprint('comments_bp', __name__)

@comments_bp.route('/posts/<string:post_id>/comments', methods=['POST'])
@jwt_required()
@api_doc(
    summary="댓글 생성",
    description="특정 게시글에 새로운 댓글을 작성합니다. 댓글 생성 후 게시물 작성자 및 멘션된 사용자에게 알림이 생성됩니다.",
    tags=["comments"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.VALIDATION_ERROR,
    CommonErrors.RESOURCE_NOT_FOUND,
    CommentErrors.COMMENT_CREATION_FAILED
)
@request_examples(RequestExamples.CREATE_COMMENT)
@response_examples({
    "name": "comment_created",
    "summary": "댓글 생성 성공",
    "description": "새로 생성된 댓글 정보",
    "value": {
        "comment_id": "comment_123",
        "post_id": "post_456",
        "user_id": "user_789",
        "text": "새로운 댓글 내용입니다.",
        "created_at": "2023-12-10T12:00:00Z",
        "like_count": 0,
        "is_liked": False
    }
})
def create_comment(post_id: str):
    """
    특정 게시글에 새로운 댓글을 작성합니다.
    - 성공 시, 생성된 댓글 정보를 201 Created 상태 코드와 함께 반환합니다.
    - 댓글 생성 후 게시물 작성자 및 멘션된 사용자에게 알림이 생성됩니다.
    """
    comment_service = current_app.services['comments']
    comment_events = current_app.services['comment_events']
    mention_service = current_app.services.get('comment_mentions')  # 멘션 서비스 (없으면 None)
    
    user_id = get_jwt_identity()

    # 1차: 입력 검증
    try:
        data = CommentCreateSchema().load(request.get_json())
    except ValidationError as err:
        status, body = build_error('VALIDATION_ERROR', details=err.messages)
        return jsonify(body), status

    text = data['text']

    # 2차: 댓글 생성 + 멘션 + 이벤트 처리
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
    except ValueError as e:  # 게시물 없음 등
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"댓글 생성 중 오류 발생 (post_id: {post_id}): {e}", exc_info=True)
        status, body = build_error('RECORD_CREATION_FAILED', message="댓글 생성 중 오류가 발생했습니다.")
        return jsonify(body), status

@comments_bp.route('/posts/<string:post_id>/comments', methods=['GET'])
@jwt_required(optional=True)
@api_doc(
    summary="댓글 목록 조회",
    description="특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다. 로그인 사용자의 경우 좋아요 상태도 함께 반환됩니다.",
    tags=["comments"]
)
@error_responses(
    CommonErrors.INTERNAL_SERVER_ERROR
)
@request_examples(RequestExamples.PAGINATION_QUERY)
@response_examples(ResponseExamples.PAGINATED_LIST)
def get_comments(post_id: str):
    """
    특정 게시글의 댓글 목록을 페이지네이션으로 조회합니다.
    """
    comment_service = current_app.services['comments']
    
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    
    try:
        comments, next_cursor = comment_service.get_comments_for_post(post_id, limit, cursor)

        # is_liked enrichment (batch) if user authenticated
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
@api_doc(
    summary="댓글 삭제",
    description="특정 댓글을 삭제합니다. 작성자 본인만 삭제할 수 있으며, 성공 시 게시물의 댓글 수가 감소합니다.",
    tags=["comments"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommonErrors.PERMISSION_DENIED,
    CommonErrors.RESOURCE_NOT_FOUND
)
@response_examples(ResponseExamples.SUCCESS_DELETED)
def delete_comment(comment_id: str):
    """
    특정 댓글을 삭제합니다. (작성자 본인만 가능)
    - 성공 시, 게시물의 댓글 수가 1 감소합니다.
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
@api_doc(
    summary="댓글 좋아요 토글",
    description="특정 댓글의 좋아요를 누르거나 취소합니다. 좋아요를 누른 경우에만 댓글 작성자에게 알림이 생성됩니다.",
    tags=["comments"]
)
@error_responses(
    CommonErrors.MISSING_JWT,
    CommonErrors.INVALID_JWT,
    CommentErrors.COMMENT_NOT_FOUND,
    CommentErrors.COMMENT_CREATION_FAILED
)
@response_examples({
    "name": "like_toggled",
    "summary": "좋아요 상태 변경 성공",
    "description": "댓글 좋아요 상태가 성공적으로 변경됨",
    "value": {"message": "좋아요 상태가 변경되었습니다."}
})
def toggle_comment_like(comment_id: str):
    """
    특정 댓글의 좋아요를 누르거나 취소합니다.
    """
    comment_service = current_app.services['comments']
    comment_events = current_app.services['comment_events']
    
    user_id = get_jwt_identity()
    try:
        # 1. 좋아요 토글 (순수한 CRUD, 이벤트 데이터 반환)
        like_data = comment_service.toggle_comment_like(user_id, comment_id)
        if not like_data:
            raise Exception("LIKE_TOGGLE_INTERNAL_ERROR")

        # 2. 좋아요 이벤트 처리 (알림 생성) - action 필드 사용
        liked_now = (like_data.get('action') == 'liked')
        if liked_now:
            comment_events.handle_comment_liked(like_data)

        return jsonify({
            "message": "좋아요 상태가 변경되었습니다.",
            "liked": liked_now,
            "comment_id": comment_id
        }), 200
        
    except ValueError as e:
        status, body = build_error('NOT_FOUND', message=str(e))
        return jsonify(body), status
    except Exception as e:
        logging.error(f"댓글 좋아요 처리 중 오류 발생 (comment_id: {comment_id}): {e}", exc_info=True)
        status, body = build_error('UPDATE_FAILED', message="좋아요 처리 중 오류가 발생했습니다.")
        return jsonify(body), status