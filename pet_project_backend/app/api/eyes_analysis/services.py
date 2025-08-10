import io
from flask import current_app
from firebase_admin import storage

# Firestore 저장을 위한 공용 서비스 import
from app.services.firestore_service import save_analysis_result


def analyze_eye_image_from_gcs(user_id, pet_id, file_path):
    """
    GCS에 저장된 이미지 파일을 다운로드하여 분석하고 결과를 저장합니다.
    """
    # app context에서 미리 준비된 서비스들을 가져옵니다.
    eye_analyzer = current_app.services['eye_analyzer']
    
    # 1. GCS에서 이미지 파일을 메모리로 다운로드합니다.
    # 1. GCS에서 이미지 파일을 메모리로 다운로드합니다.
    try:
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        image_bytes = blob.download_as_bytes() # image_bytes는 순수한 내용물입니다.
    except Exception as e:
        # ...
        raise RuntimeError("GCS에서 파일을 가져오는 데 실패했습니다.")

    # 2. [수정됨] 다운로드한 '내용물'을 AI 분석가에게 그대로 전달합니다.
    # 이전에 io.BytesIO(image_bytes)로 감쌌던 부분을 제거합니다.
    final_disease_name, probability, all_predictions = eye_analyzer.predict(image_bytes)

    # 3. Firestore에 저장할 데이터를 구성합니다.
    result_data = {
        'pet_id': pet_id,
        'analysis_type': 'eye',
        'image_url': f"https://storage.googleapis.com/{bucket.name}/{file_path}", # GCS 공개 URL
        'result': {
            'final_disease_name': final_disease_name,
            'probability': probability
        },
        'raw_predictions': all_predictions
    }
    
    # 4. 분석 결과를 Firestore에 저장합니다.
    result_id = save_analysis_result('analysis_history', user_id, result_data)
    
    # 5. 프론트엔드에 전달할 최종 결과를 반환합니다.
    return {
        'analysis_id': result_id,
        'disease_name': final_disease_name,
        'probability': f"{probability:.2%}"
    }