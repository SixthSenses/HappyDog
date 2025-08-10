import datetime
from firebase_admin import firestore
from flask import current_app

def save_analysis_result(collection_name, user_id, data):
    """분석 결과를 Firestore에 저장하고 문서 ID를 반환합니다."""
    try:
        db = firestore.client()
        
        data['created_at'] = datetime.datetime.now(datetime.timezone.utc)
        data['user_id'] = user_id
        
        update_time, doc_ref = db.collection(collection_name).add(data)
        
        current_app.logger.info(f"✅ Data saved to Firestore with ID: {doc_ref.id}")
        return doc_ref.id

    except Exception as e:
        current_app.logger.error(f"🛑 Error saving to Firestore: {e}")
        return None