# app/api/uploads/routes.py

import logging
from flask import request, jsonify, Blueprint, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError

# 'uploads' 기능을 위한 새로운 블루프린트를 생성합니다.
# 이 블루프린트에 속한 모든 API는 '/api/uploads' 라는 접두사 URL을 갖게 됩니다.
uploads_bp = Blueprint('uploads', __name__)

@uploads_bp.route('/url', methods=['POST'])
@jwt_required()
def get_upload_url():
    """
    모든 파일 업로드를 위한 범용 Pre-signed URL을 발급합니다.
    클라이언트는 이 API를 먼저 호출하여 업로드할 권한이 있는 임시 URL을 받아야 합니다.
    """
    # 요청 헤더의 JWT에서 현재 로그인된 사용자의 ID를 가져옵니다.
    user_id = get_jwt_identity()
    
    # 요청 본문이 JSON 형식인지 확인하고 데이터를 파싱합니다.
    try:
        data = request.get_json()
        if not data:
            raise ValidationError("요청 본문이 비어있거나 JSON 형식이 아닙니다.")
        
        # 클라이언트로부터 어떤 종류의 파일을 올릴지(upload_type)와
        # 원본 파일명(filename), 파일 타입(content_type)을 받습니다.
        upload_type = data['upload_type']
        filename = data['filename']
        content_type = data['content_type']

    except (ValidationError, KeyError) as e:
        # 필수 파라미터가 누락되었거나 형식이 잘못된 경우 400 에러를 반환합니다.
        logging.warning(f"URL 발급 요청 실패 (잘못된 파라미터): {e}")
        return jsonify({
            "error_code": "INVALID_PARAMETERS", 
            "message": "필수 파라미터가 누락되었거나 형식이 올바르지 않습니다: 'upload_type', 'filename', 'content_type'가 필요합니다."
        }), 400

    # Flask 앱에 등록된 StorageService 인스턴스를 가져옵니다.
    storage_service = current_app.services['storage']
    
    try:
        # StorageService를 호출하여 Pre-signed URL을 생성합니다.
        url_info = storage_service.generate_upload_url(user_id, upload_type, filename, content_type)
        
        # 성공적으로 생성된 URL 정보를 클라이언트에 반환합니다.
        return jsonify(url_info), 200
    
    except ValueError as e:
        # 'upload_type'이 유효하지 않은 경우(service에 정의되지 않은 경우) 400 에러를 반환합니다.
        logging.warning(f"URL 발급 요청 실패 (잘못된 업로드 타입): {e}")
        return jsonify({"error_code": "INVALID_UPLOAD_TYPE", "message": str(e)}), 400
    
    except Exception as e:
        # 그 외 예측하지 못한 서버 내부 오류 발생 시 500 에러를 반환합니다.
        logging.error(f"Pre-signed URL 생성 중 서버 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "URL_GENERATION_FAILED", "message": "URL 생성 중 서버 오류가 발생했습니다."}), 500
