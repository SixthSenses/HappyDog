from firebase_admin import firestore
from app.models.pet import Pet

db = firestore.client()

def register_pet(owner_id: str, pet_data: dict) -> Pet:
    pets_collection = db.collection('pets')
    
    # Firestore에 저장할 데이터 준비
    data_to_save = pet_data.copy()
    data_to_save['owner_id'] = owner_id
    
    # 날짜 객체를 isoformat 문자열로 변환
    data_to_save['birth_date'] = data_to_save['birth_date'].isoformat()
    
    update_time, doc_ref = pets_collection.add(data_to_save)
    
    # 반환할 Pet 객체 생성
    new_pet = Pet(
        id=doc_ref.id,
        owner_id=owner_id,
        name=pet_data['name'],
        breed=pet_data['breed'],
        birth_date=pet_data['birth_date']
    )
    return new_pet