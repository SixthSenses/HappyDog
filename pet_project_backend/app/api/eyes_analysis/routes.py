# /app/api/eyes_analysis/routes.py

from flask import Blueprint, request, jsonify, current_app

# 이 블루프린트에서는 더 이상 services를 직접 import하지 않습니다.
# 모든 서비스는 current_app.services를 통해 접근합니다.

eyes_analysis_bp = Blueprint('eyes_analysis_bp', __name__, url_prefix='/api/eyes-analysis')


@eyes_analysis_bp.route('/upload-url', methods=['POST'])
def get_eye_analysis_upload_url():
    """
    안구 분석용 이미지 업로드를 위한 Pre-signed URL을 요청합니다.
    """
    data = request.get_json()
    filename = data.get('filename')
    content_type = data.get('contentType')

    if not all([filename, content_type]):
        return jsonify({"error": "filename과 contentType이 필요합니다."}), 400

    # JWT 등에서 사용자 ID를 가져옵니다 (지금은 임시값 사용)
    user_id = "temp_user_12345"
    
    # app context에 등록된 storage service를 사용합니다.
    storage_service = current_app.services['storage']
    
    try:
        # 'eye_analysis' 타입으로 업로드 URL 생성 요청
        upload_info = storage_service.generate_upload_url(
            user_id=user_id,
            upload_type="eye_analysis", # 이 타입을 storage_service에 추가해야 할 수 있습니다.
            filename=filename,
            content_type=content_type
        )
        return jsonify(upload_info), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Upload URL 생성 실패: {e}")
        return jsonify({"error": "URL 생성에 실패했습니다."}), 500


@eyes_analysis_bp.route('/results', methods=['POST'])
def request_eye_analysis():
    """
    클라이언트가 GCS에 업로드를 완료한 후, 해당 파일의 분석을 요청합니다.
    """
    data = request.get_json()
    file_path = data.get('filePath') # generate_upload_url이 반환했던 파일 경로
    pet_id = data.get('petId')

    if not all([file_path, pet_id]):
        return jsonify({"error": "filePath와 petId가 필요합니다."}), 400

    # JWT 등에서 사용자 ID를 가져옵니다.
    user_id = "temp_user_12345"

    # app context에 등록된 eye_analyzer를 사용합니다.
    # 이 부분은 직접 services.py를 호출하여 로직을 실행하도록 변경합니다.
    from . import services
    
    try:
        result = services.analyze_eye_image_from_gcs(
            user_id=user_id,
            pet_id=pet_id,
            file_path=file_path
        )
        return jsonify(result), 200
    except Exception as e:
    # logger.exception은 에러의 Traceback 전체를 상세하게 출력해줍니다.
        current_app.logger.exception("안구 분석 실패:") 
        return jsonify({"error": "분석 처리 중 오류가 발생했습니다."}), 500