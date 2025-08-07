# app/api/mungstagram/routes.py
import logging
from flask import Blueprint, request, jsonify, current_app, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

from app.api.mungstagram.schemas import (
    PostCreateSchema, PostUpdateSchema, PostResponseSchema,
    CartoonJobCreateSchema, CartoonJobResponseSchema
)
from .services import mungstagram_service

mungstagram_bp = Blueprint('mungstagram_bp', __name__)

# --- Phase 1: 게시물 CRUD ---
@mungstagram_bp.route('/posts', methods=['POST'])
@jwt_required()
def create_post():
    user_id = get_jwt_identity()
    try:
        post_data = PostCreateSchema().load(request.get_json())
        storage_service = current_app.services['storage']
        new_post = mungstagram_service.create_post(user_id, post_data, storage_service)
        return jsonify(PostResponseSchema().dump(new_post)), 201
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except ValueError as e:
        return jsonify({"error_code": "RESOURCE_NOT_FOUND", "message": str(e)}), 404
    except Exception as e:
        logging.error(f"게시물 생성 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 생성 중 오류가 발생했습니다."}), 500

@mungstagram_bp.route('/posts', methods=['GET'])
@jwt_required()
def get_posts():
    user_id = get_jwt_identity()
    limit = request.args.get('limit', 10, type=int)
    cursor = request.args.get('cursor', None, type=str)
    try:
        posts, next_cursor = mungstagram_service.get_posts(user_id, limit, cursor)
        return jsonify({
            "posts": PostResponseSchema(many=True).dump(posts),
            "next_cursor": next_cursor
        }), 200
    except Exception as e:
        logging.error(f"게시물 목록 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "게시물 목록 조회 중 오류가 발생했습니다."}), 500

@mungstagram_bp.route('/posts/<string:post_id>', methods=['GET'])
@jwt_required()
def get_post(post_id):
    user_id = get_jwt_identity()
    post = mungstagram_service.get_post_by_id(post_id, user_id)
    if not post:
        return jsonify({"error_code": "POST_NOT_FOUND", "message": "게시물을 찾을 수 없습니다."}), 404
    return jsonify(PostResponseSchema().dump(post)), 200

@mungstagram_bp.route('/posts/<string:post_id>', methods=['PUT'])
@jwt_required()
def update_post(post_id):
    user_id = get_jwt_identity()
    try:
        data = PostUpdateSchema().load(request.get_json())
        updated_post = mungstagram_service.update_post(post_id, user_id, data['text'])
        if not updated_post:
            return jsonify({"error_code": "FORBIDDEN_OR_NOT_FOUND", "message": "수정 권한이 없거나 게시물이 존재하지 않습니다."}), 403
        return jsonify(PostResponseSchema().dump(updated_post)), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400

@mungstagram_bp.route('/posts/<string:post_id>', methods=['DELETE'])
@jwt_required()
def delete_post(post_id):
    user_id = get_jwt_identity()
    storage_service = current_app.services['storage']
    success = mungstagram_service.delete_post(post_id, user_id, storage_service)
    if not success:
        return jsonify({"error_code": "FORBIDDEN_OR_NOT_FOUND", "message": "삭제 권한이 없거나 게시물이 존재하지 않습니다."}), 403
    return Response(status=204)

# --- Phase 2: 좋아요 ---
@mungstagram_bp.route('/posts/<string:post_id>/like', methods=['POST'])
@jwt_required()
def add_like(post_id):
    user_id = get_jwt_identity()
    try:
        mungstagram_service.add_like(user_id, post_id)
        return jsonify({"message": "좋아요가 추가되었습니다."}), 200
    except ValueError as e:
        return jsonify({"error_code": "POST_NOT_FOUND", "message": str(e)}), 404

@mungstagram_bp.route('/posts/<string:post_id>/like', methods=['DELETE'])
@jwt_required()
def remove_like(post_id):
    user_id = get_jwt_identity()
    mungstagram_service.remove_like(user_id, post_id)
    return jsonify({"message": "좋아요가 취소되었습니다."}), 200

# --- Phase 3: 만화 생성 ---
@mungstagram_bp.route('/cartoon-jobs', methods=['POST'])
@jwt_required()
def create_cartoon_job():
    user_id = get_jwt_identity()
    try:
        job_data = CartoonJobCreateSchema().load(request.get_json())
        storage_service = current_app.services['storage']
        new_job = mungstagram_service.create_cartoon_job(user_id, job_data, storage_service)
        return jsonify(CartoonJobResponseSchema().dump(new_job)), 202
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400

@mungstagram_bp.route('/cartoon-jobs/<string:job_id>', methods=['GET'])
@jwt_required()
def get_cartoon_job(job_id):
    job = mungstagram_service.get_cartoon_job_by_id(job_id)
    if not job:
        return jsonify({"error_code": "JOB_NOT_FOUND", "message": "작업을 찾을 수 없습니다."}), 404
    return jsonify(CartoonJobResponseSchema().dump(job)), 200
