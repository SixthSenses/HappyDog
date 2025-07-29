from flask import Blueprint, request, jsonify, g
from marshmallow import ValidationError
from app.schemas.pet_schema import PetSchema
from . import services as pet_services
from app.core.security import jwt_required

pets_bp = Blueprint('pets', __name__)

# 표준: 스키마 인스턴스를 모듈 레벨에서 생성
pet_schema = PetSchema()

@pets_bp.route('/', methods=['POST'])
@jwt_required
def create_pet():
    json_data = request.get_json()
    if not json_data:
        return jsonify({"error": "No input data provided"}), 400

    try:
        validated_data = pet_schema.load(json_data)
        owner_id = g.user['user_id']
        
        new_pet = pet_services.register_pet(owner_id=owner_id, pet_data=validated_data)
        
        return pet_schema.dump(new_pet), 201

    except ValidationError as err:
        return jsonify(err.messages), 400
    except Exception as e:
        print(e)
        return jsonify({"error": "An internal error occurred"}), 500