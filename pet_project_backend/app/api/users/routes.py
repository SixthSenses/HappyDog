# app/api/users/routes.py
import logging
from flask import Blueprint, request, jsonify, Response,current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError


from app.api.users.schemas import (
    UserPublicResponseSchema,
    FCMTokenSchema,
    NotificationPreferencesSchema,
    SelectedPetUpdateSchema,
)

users_bp = Blueprint('users_bp', __name__)

@users_bp.route('/<string:user_id>', methods=['GET'])
@jwt_required(optional=True)
def get_user_profile(user_id: str):
    user_service = current_app.services['users']
    """특정 사용자의 공개 프로필 정보(게시물 수 포함)를 조회합니다."""
    try:
        # 서비스 함수 이름을 get_user_profile로 변경
        user_profile = user_service.get_user_profile(user_id)
        if not user_profile:
            return jsonify({"error_code": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404
        
        return jsonify(UserPublicResponseSchema().dump(user_profile)), 200
    except Exception as e:
        logging.error(f"사용자 프로필 조회 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "PROFILE_FETCH_FAILED", "message": "프로필 조회 중 오류가 발생했습니다."}), 500


@users_bp.route('/me/profile-image', methods=['PATCH'])
@jwt_required()
def update_my_profile_image():
    user_service = current_app.services['users']
    """
    현재 로그인된 사용자의 프로필 이미지를 업데이트합니다.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    file_path = data.get('file_path')

    if not file_path:
        return jsonify({"error_code": "INVALID_PAYLOAD", "message": "'file_path' 필드가 필요합니다."}), 400
    
    try:
        updated_user = user_service.update_user_profile_image(user_id, file_path)
        if not updated_user:
             return jsonify({"error_code": "USER_NOT_FOUND", "message": "사용자를 찾을 수 없습니다."}), 404
        
        # 전체 사용자 정보 대신 업데이트된 URL만 반환하거나, 혹은 공개 스키마를 사용할 수 있습니다.
        return jsonify(UserPublicResponseSchema().dump(updated_user)), 200
    except Exception as e:
        logging.error(f"프로필 이미지 업데이트 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "INTERNAL_SERVER_ERROR", "message": "프로필 이미지 업데이트 중 서버 오류가 발생했습니다."}), 500


@users_bp.route('/me', methods=['DELETE'])
@jwt_required()
def delete_my_account():
    user_service = current_app.services['users']
    """
    현재 로그인된 사용자 본인의 계정을 영구적으로 삭제합니다.
    """
    user_id = get_jwt_identity()
    try:
        user_service.delete_user_account(user_id)
        # 성공 시에는 본문(body) 없이 204 상태 코드만 반환하는 것이 RESTful API 표준
        return Response(status=204)
    except Exception as e:
        logging.error(f"회원 탈퇴 처리 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "ACCOUNT_DELETION_FAILED", "message": "회원 탈퇴 처리 중 서버 오류가 발생했습니다."}), 500

@users_bp.route('/me/notification-preferences', methods=['GET'])
@jwt_required()
def get_my_notification_preferences():
    user_service = current_app.services['users']
    user_id = get_jwt_identity()
    try:
        prefs = user_service.get_notification_preferences(user_id) or {}
        return jsonify(prefs), 200
    except Exception as e:
        logging.error(f"알림 설정 조회 오류: {e}", exc_info=True)
        return jsonify({"error_code": "FETCH_FAILED", "message": "알림 설정 조회 중 오류가 발생했습니다."}), 500

@users_bp.route('/me/notification-preferences', methods=['PATCH'])
@jwt_required()
def update_my_notification_preferences():
    user_service = current_app.services['users']
    user_id = get_jwt_identity()
    try:
        payload = NotificationPreferencesSchema().load(request.get_json() or {})
        updated = user_service.update_notification_preferences(user_id, payload)
        return jsonify(updated), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"알림 설정 업데이트 오류: {e}", exc_info=True)
        return jsonify({"error_code": "UPDATE_FAILED", "message": "알림 설정 업데이트 중 오류가 발생했습니다."}), 500


@users_bp.route('/me/fcm-token', methods=['POST'])
@jwt_required()
def register_fcm_token():
    user_service = current_app.services['users']
    """
    클라이언트의 FCM 토큰을 등록/업데이트합니다.
    """
    user_id = get_jwt_identity()
    try:
        data = FCMTokenSchema().load(request.get_json())
        user_service.update_fcm_token(user_id, data['fcm_token'])
        return jsonify({"message": "FCM 토큰이 성공적으로 업데이트되었습니다."}), 200
    except ValidationError as err:
        return jsonify({"error_code": "VALIDATION_ERROR", "details": err.messages}), 400
    except Exception as e:
        logging.error(f"FCM 토큰 업데이트 중 오류 발생: {e}", exc_info=True)
        return jsonify({"error_code": "UPDATE_FAILED", "message": "FCM 토큰 업데이트 중 서버 오류가 발생했습니다."}), 500


@users_bp.route('/<string:user_id>/summary', methods=['GET'])
@jwt_required(optional=True)
def get_public_user_summary(user_id: str):
    """
    [공개] 멍스타그램 등에서 타 사용자의 공개 프로필과 특정 반려견 요약 정보를 제공합니다.
    쿼리 파라미터:
    - pet_id (optional): 공개 반려견 ID. 제공 시 반려견 요약(name, breed, birthdate, age_months)을 포함합니다.

    응답 예:
    {
      "user": {"user_id","nickname","profile_image_url","post_count"},
      "pet": {"pet_id","name","breed","birthdate","age_months"} | null
    }
    """
    from app.utils.datetime_utils import DateTimeUtils
    pet_id = request.args.get('pet_id')
    user_service = current_app.services['users']
    pet_service = current_app.services['pets']

    try:
        # 공개 사용자 프로필(게시물 수 포함)
        user_payload = user_service.get_user_profile(user_id)
        if not user_payload:
            return jsonify({"error_code": "USER_NOT_FOUND", "message": "해당 사용자를 찾을 수 없습니다."}), 404

        pet_summary = None
        if pet_id:
            try:
                pet_public = pet_service.get_public_pet_profile(pet_id)
                # 요약 필드 선택 + 나이(개월) 계산
                birthdate = pet_public.get('birthdate')
                try:
                    age_months = DateTimeUtils.calculate_age_months(birthdate) if birthdate else None
                except Exception:
                    age_months = None
                pet_summary = {
                    'pet_id': pet_public.get('pet_id'),
                    'name': pet_public.get('name'),
                    'breed': pet_public.get('breed'),
                    'birthdate': pet_public.get('birthdate'),
                    'age_months': age_months,
                }
            except FileNotFoundError:
                pet_summary = None

        return jsonify({
            'user': UserPublicResponseSchema().dump(user_payload),
            'pet': pet_summary
        }), 200
    except Exception as e:
        logging.error(f"Public user summary error (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"error_code": "SUMMARY_FETCH_FAILED", "message": "요약 정보 조회 중 오류가 발생했습니다."}), 500

@users_bp.route('/me/summary', methods=['GET'])
@jwt_required(optional=True)
def get_me_summary():
    """
    프로필/마이페이지/멍스타그램 프로필에서 공통으로 필요한 요약 정보를 한 번에 제공합니다.
    요청 파라미터:
    - selected_pet_id (optional): 앱의 TokenManager 선택 펫 ID
    응답:
    {
      user: { user_id, nickname, profile_image_url, post_count? },
      pet: { ...PetPublicProfileResponse ... } | null,
      settings: { ...PetCareSettings } | null
    }
    """
    from app.api.pets.schemas import PetPublicProfileResponseSchema
    from app.utils.datetime_utils import DateTimeUtils
    selected_pet_id = request.args.get('selected_pet_id')
    user_service = current_app.services['users']
    pet_service = current_app.services['pets']
    pet_care_setting_service = current_app.services['pet_care_settings']

    try:
        # 현재 로그인 사용자의 공개 프로필(게시물 수 포함)
        current_user_id = None
        try:
            from flask_jwt_extended import get_jwt_identity
            current_user_id = get_jwt_identity()
        except Exception:
            current_user_id = None

        user_payload = None
        if current_user_id:
            user_payload = user_service.get_user_profile(current_user_id)

        pet_payload = None
        settings_payload = None
        if selected_pet_id:
            try:
                pet_payload = pet_service.get_public_pet_profile(selected_pet_id)
            except FileNotFoundError:
                pet_payload = None
            try:
                settings_payload = pet_care_setting_service.get_settings(selected_pet_id)
            except FileNotFoundError:
                settings_payload = None

        # age_months 보강 (요청 반영)
        pet_resp = PetPublicProfileResponseSchema().dump(pet_payload) if pet_payload else None
        if pet_resp and pet_payload and pet_payload.get('birthdate'):
            try:
                pet_resp['age_months'] = DateTimeUtils.calculate_age_months(pet_payload.get('birthdate'))
            except Exception:
                pet_resp['age_months'] = None

        return jsonify({
            'user': UserPublicResponseSchema().dump(user_payload) if user_payload else None,
            'pet': pet_resp,
            'settings': pet_care_setting_service and settings_payload or None
        }), 200
    except Exception as e:
        logging.error(f"Summary endpoint error: {e}", exc_info=True)
        return jsonify({"error_code": "SUMMARY_FETCH_FAILED", "message": "요약 정보 조회 중 오류가 발생했습니다."}), 500


# ----------------------- Selected Pet Endpoints -----------------------
@users_bp.route('/me/selected-pet', methods=['GET'])
@jwt_required()
def get_my_selected_pet():
    """
    인증 사용자 기준 현재 선택 펫 조회.
    200: { pet_id, name?, profile_image_url?, updated_at? }
    204: 선택 펫 없음
    404: 기록은 있으나 해당 펫이 삭제됨 등
    """
    user_service = current_app.services['users']
    pet_service = current_app.services['pets']
    user_id = get_jwt_identity()
    try:
        record = user_service.get_selected_pet(user_id)
        if not record or not record.get('pet_id'):
            return Response(status=204)

        pet_id = record['pet_id']
        # 펫 존재 여부 확인 (공개 프로필로 충분)
        try:
            pet_public = pet_service.get_public_pet_profile(pet_id)
        except FileNotFoundError:
            # 기록은 있으나 펫이 삭제된 경우
            return jsonify({"message": "선택된 반려동물을 찾을 수 없습니다."}), 404
        # 소유권 상실 케이스 (기록은 있으나 더 이상 소유하지 않음)
        if pet_public.get('user_id') != user_id:
            return jsonify({"message": "선택된 반려동물에 대한 소유 권한이 없습니다."}), 403

        payload = {
            'pet_id': pet_id,
            'name': pet_public.get('name'),
            'profile_image_url': pet_public.get('profile_image_url'),
            'updated_at': record.get('updated_at'),
        }
        return jsonify(payload), 200
    except Exception as e:
        logging.error(f"선택 펫 조회 오류 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"message": "선택 펫 조회 중 오류가 발생했습니다."}), 500


@users_bp.route('/me/selected-pet', methods=['PATCH'])
@jwt_required()
def update_my_selected_pet():
    """
    현재 로그인된 사용자의 선택 펫을 설정/갱신합니다.
    Body: { pet_id: uuid }
    200: { pet_id }
    400: 잘못된 UUID
    403: 소유권 불일치
    404: 존재하지 않는 pet
    """
    user_service = current_app.services['users']
    pet_service = current_app.services['pets']

    user_id = get_jwt_identity()
    try:
        data = SelectedPetUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return jsonify({"message": "유효하지 않은 요청 본문입니다.", "errors": err.messages}), 400
    except Exception:
        return jsonify({"message": "잘못된 요청 형식입니다."}), 400

    pet_id = data['pet_id']

    # 존재/소유권 검사
    try:
        pet_owned = pet_service.get_pet_by_id_and_owner(pet_id, user_id)
    except Exception as e:
        logging.error(f"펫 조회 중 오류 (pet_id: {pet_id}, user_id: {user_id}): {e}", exc_info=True)
        return jsonify({"message": "선택 펫 설정 중 오류가 발생했습니다."}), 500

    if pet_owned is None:
        # 펫이 없거나 소유권이 아님. 존재여부를 구분하기 위해 공개 조회 시도
        try:
            pet_service.get_public_pet_profile(pet_id)
            # 존재하지만 소유권 없음
            return jsonify({"message": "해당 반려동물을 선택할 권한이 없습니다."}), 403
        except FileNotFoundError:
            return jsonify({"message": "해당 반려동물을 찾을 수 없습니다."}), 404

    # 멱등 저장
    try:
        user_service.set_selected_pet(user_id, pet_id)
        return jsonify({"pet_id": pet_id}), 200
    except Exception as e:
        logging.error(f"선택 펫 저장 실패 (user_id: {user_id}, pet_id: {pet_id}): {e}", exc_info=True)
        return jsonify({"message": "선택 펫 저장 중 오류가 발생했습니다."}), 500