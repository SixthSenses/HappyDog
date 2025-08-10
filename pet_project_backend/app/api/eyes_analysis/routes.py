# /app/api/eyes_analysis/routes.py

from flask import Blueprint, request, jsonify, current_app
# [피드백 1 반영] JWT 관련 모듈 임포트
from flask_jwt_extended import jwt_required, get_jwt_identity

# [피드백 2 반영] 이 파일에는 이제 '/results' API만 남습니다.
eyes_analysis_bp = Blueprint('eyes_analysis_bp', __name__, url_prefix='/api/eyes-analysis')


@eyes_analysis_bp.route('/results', methods=['POST'])
@jwt_required() # [피드백 1 반영] 로그인이 필요한 API로 설정
def request_eye_analysis():
    """
    클라이언트가 GCS에 업로드를 완료한 후, 해당 파일의 분석을 요청합니다.
    """
    data = request.get_json()
    file_path = data.get('filePath') # generate_upload_url이 반환했던 파일 경로
    pet_id = data.get('petId')

    if not all([file_path, pet_id]):
        return jsonify({"error": "filePath와 petId가 필요합니다."}), 400

    # [피드백 1 반영] 임시 ID 대신, 로그인 토큰에서 실제 사용자 ID를 가져옵니다.
    user_id = get_jwt_identity()

    # services.py의 함수를 호출하여 실제 분석 로직을 수행합니다.
    from . import services
    
    try:
        result = services.analyze_eye_image_from_gcs(
            user_id=user_id,
            pet_id=pet_id,
            file_path=file_path
        )
        return jsonify(result), 200
    except Exception as e:
        # 에러 발생 시, 상세한 Traceback을 터미널에 기록합니다.
        current_app.logger.exception("안구 분석 실패:") 
        return jsonify({"error": "분석 처리 중 오류가 발생했습니다."}), 500