# app/services/openai_service.py
import logging
import os
import uuid
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from urllib.parse import urlparse, unquote, quote
from flask import Flask
from openai import OpenAI

class OpenAIService:
    """
    OpenAI API 연동을 담당하는 서비스 클래스.
    만화 생성 및 이미지 처리 기능을 제공합니다.
    """
    
    def __init__(self):
        """
        OpenAI 클라이언트를 None으로 초기화합니다.
        실제 클라이언트는 init_app 메서드를 통해 설정됩니다.
        """
        self.client = None
        
    def init_app(self, app: Flask):
        """
        Flask 앱 초기화 과정에서 호출되어 OpenAI 클라이언트를 설정합니다.
        
        :param app: Flask 애플리케이션 객체
        """
        api_key = app.config.get('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY 설정이 .env 파일에 필요합니다.")
            
        self.client = OpenAI(api_key=api_key)
        logging.info("OpenAIService: OpenAI API 서비스가 성공적으로 초기화되었습니다.")
    
    def generate_cartoon(self, image_url: str, user_text: str, storage_service=None) -> Dict[str, Any]:
        """
        사용자가 업로드한 이미지와 텍스트를 기반으로 4컷 만화를 생성합니다.
        GPT-4 Vision으로 이미지를 분석한 후 DALL-E 3로 만화를 생성합니다.
        
        :param image_url: 사용자가 업로드한 원본 이미지 URL (Firebase Storage URL)
        :param user_text: 사용자가 입력한 텍스트
        :param storage_service: StorageService 인스턴스 (Signed URL 생성 및 DALL-E 결과 저장용)
        :return: 생성된 이미지 정보를 담은 딕셔너리
        
        Note:
            - GPT-4o는 Signed URL을 통해 Firebase Storage에 직접 접근
            - DALL-E가 반환한 임시 URL은 만료되므로 Firebase Storage에 영구 저장
        """
        if not self.client:
            raise RuntimeError("OpenAIService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
        
        if not storage_service:
            raise RuntimeError("StorageService가 필요합니다. storage_service 파라미터를 전달해주세요.")
        
        try:
            # 1단계: Signed URL 생성 (OpenAI가 직접 접근 가능)
            logging.info(f"원본 이미지 URL: {image_url}")
            
            try:
                # URL에서 파일 경로 추출
                file_path = self._extract_file_path_from_url(image_url)
                logging.info(f"추출된 파일 경로: {file_path}")
                
                # Signed URL 생성 (2시간 유효)
                signed_url = storage_service.get_signed_url(file_path, expiration_hours=2)
                logging.info(f"Signed URL 생성 완료 (만료: 2시간)")
            except FileNotFoundError as e:
                logging.error(f"이미지 파일을 찾을 수 없습니다: {e}")
                raise RuntimeError(f"원본 이미지를 찾을 수 없습니다: {str(e)}")
            except Exception as e:
                logging.error(f"Signed URL 생성 실패: {e}", exc_info=True)
                raise RuntimeError(f"이미지 URL 생성 실패: {str(e)}")
            
            # 2단계: GPT-4 Vision으로 이미지 분석 (Signed URL 사용, 재시도 포함)
            image_description = None
            last_err = None
            for attempt in range(3):
                try:
                    logging.info(f"GPT-4o 이미지 분석 시도 {attempt+1}/3")
                    image_description = self._analyze_image_with_gpt4_vision(signed_url)
                    logging.info(f"GPT-4o 이미지 분석 완료: {image_description[:100]}...")
                    break
                except Exception as e:
                    last_err = e
                    logging.warning(f"GPT-4o 분석 재시도 {attempt+1}/3 실패: {e}")
            
            if image_description is None:
                logging.warning("이미지 분석이 3회 모두 실패하여 기본 설명으로 진행합니다.")
                image_description = "귀여운 반려동물이 있는 일상적인 장면"

            # 3단계: 분석 결과와 사용자 텍스트로 만화 프롬프트 구성
            cartoon_prompt = self._build_cartoon_prompt_from_analysis(image_description, user_text)

            # 4단계: DALL-E 3로 4컷 만화 생성 (재시도 포함)
            last_err = None
            dall_e_temp_url = None
            for attempt in range(3):
                try:
                    response = self.client.images.generate(
                        model="dall-e-3",
                        prompt=cartoon_prompt,
                        size="1024x1024",
                        quality="standard",
                        n=1,
                    )
                    generated_image = response.data[0]
                    dall_e_temp_url = generated_image.url
                    
                    # 5단계: DALL-E 임시 URL을 Firebase Storage에 영구 저장
                    permanent_url = None
                    if storage_service and dall_e_temp_url:
                        try:
                            permanent_url = self._save_dalle_result_to_storage(
                                dall_e_temp_url, 
                                storage_service
                            )
                            logging.info(f"DALL-E 결과 이미지를 Firebase Storage에 저장 완료: {permanent_url}")
                        except Exception as e:
                            logging.error(f"DALL-E 결과 저장 실패, 임시 URL 반환: {e}")
                            permanent_url = dall_e_temp_url  # Fallback to temp URL
                    else:
                        permanent_url = dall_e_temp_url
                    
                    return {
                        "success": True,
                        "image_url": permanent_url,  # 영구 URL 반환
                        "temp_url": dall_e_temp_url,  # 디버깅용 임시 URL
                        "image_description": image_description,
                        "final_prompt": cartoon_prompt,
                        "revised_prompt": getattr(generated_image, 'revised_prompt', cartoon_prompt),
                        "model_used": "gpt-4-vision + dall-e-3"
                    }
                except Exception as e:
                    last_err = e
                    logging.warning(f"DALL-E 생성 재시도 {attempt+1}/3 실패: {e}")
            raise last_err or RuntimeError("이미지 생성 실패")

        except Exception as e:
            logging.error(f"OpenAI 만화 생성 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _extract_file_path_from_url(self, image_url: str) -> str:
        """
        Firebase Storage URL 또는 GCS URL에서 파일 경로를 추출합니다.
        
        :param image_url: Firebase Storage URL 또는 GCS URL
        :return: 파일 경로 (상대 경로)
        """
        file_path = None
        
        if "firebasestorage.googleapis.com" in image_url:
            # Firebase Storage URL 형식: https://firebasestorage.googleapis.com/v0/b/{bucket}/o/{encoded_path}?alt=media&token={token}
            try:
                file_path = image_url.split('o/')[1].split('?')[0]
                file_path = unquote(file_path)
                logging.info(f"Firebase Storage URL 파싱: {file_path}")
            except Exception as e:
                logging.error(f"Firebase Storage URL 파싱 실패: {e}")
                raise ValueError(f"잘못된 Firebase Storage URL 형식: {image_url}")
        elif "storage.googleapis.com" in image_url:
            # GCS URL 형식: https://storage.googleapis.com/{bucket}/{path}
            # 예: https://storage.googleapis.com/happydog-test.firebasestorage.app/cartoon_sources/user_id/file.jpg
            try:
                parts = image_url.split('storage.googleapis.com/')
                if len(parts) == 2:
                    # bucket/path 형태에서 bucket 제거
                    full_path = parts[1]
                    logging.debug(f"GCS URL full_path: {full_path}")
                    
                    # Bucket 이름 확인
                    # happydog-test.firebasestorage.app 또는 happydog-test.appspot.com 등
                    # 첫 번째 '/' 이후가 실제 파일 경로
                    path_parts = full_path.split('/', 1)
                    if len(path_parts) == 2:
                        bucket_name = path_parts[0]
                        file_path = path_parts[1]  # bucket 다음의 경로
                        logging.info(f"GCS URL 파싱: bucket={bucket_name}, path={file_path}")
                    else:
                        # '/'가 없으면 전체가 파일 경로 (드문 경우)
                        file_path = full_path
                        logging.warning(f"GCS URL에 bucket 구분자 없음, 전체를 경로로 사용: {file_path}")
                else:
                    raise ValueError("GCS URL 형식 오류")
            except Exception as e:
                logging.error(f"GCS URL 파싱 실패: {e}")
                raise ValueError(f"잘못된 GCS URL 형식: {image_url}")
        else:
            # 상대 경로로 가정
            file_path = image_url
            logging.info(f"상대 경로로 처리: {file_path}")
        
        if not file_path:
            raise ValueError(f"URL에서 파일 경로를 추출할 수 없습니다: {image_url}")
        
        logging.info(f"추출된 파일 경로: {file_path}")
        return file_path
    
    def _save_dalle_result_to_storage(self, dalle_temp_url: str, storage_service) -> str:
        """
        DALL-E가 반환한 임시 URL의 이미지를 다운로드하여 Firebase Storage에 영구 저장합니다.
        
        :param dalle_temp_url: DALL-E가 반환한 임시 Azure URL
        :param storage_service: StorageService 인스턴스
        :return: Firebase Storage의 영구 URL
        """
        # DALL-E 이미지 다운로드
        response = requests.get(dalle_temp_url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        
        # Firebase Storage에 업로드할 경로 생성
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_path = f"cartoon_results/{timestamp}_{unique_id}.png"
        
        # Firebase Storage에 업로드
        blob = storage_service.bucket.blob(file_path)
        blob.upload_from_string(image_bytes, content_type='image/png')
        
        # 다운로드 토큰 생성 및 설정
        download_token = str(uuid.uuid4())
        blob.metadata = {'firebaseStorageDownloadTokens': download_token}
        blob.patch()
        
        # Firebase Storage URL 생성
        bucket_name = storage_service.bucket.name
        encoded_path = quote(file_path, safe='')
        firebase_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded_path}?alt=media&token={download_token}"
        
        logging.info(f"DALL-E 결과 이미지 저장 완료: {file_path}")
        return firebase_url
    
    def _analyze_image_with_gpt4_vision(self, image_url: str) -> str:
        """
        GPT-4o를 사용하여 이미지를 분석하고 설명을 생성합니다.
        
        Signed URL을 사용하여 Firebase Storage 이미지에 접근합니다.
        
        :param image_url: 분석할 이미지 Signed URL
        :return: 이미지 분석 결과 텍스트
        """
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """이 이미지에 있는 동물들과 상황을 자세히 분석해주세요. 
                            4컷 만화로 만들기 위해 다음 정보를 포함해서 설명해주세요:
                            1. 동물의 종류, 색깔, 특징
                            2. 동물의 표정이나 자세
                            3. 배경이나 주변 환경
                            4. 전체적인 분위기나 상황
                            5. 만화로 만들 수 있는 스토리 아이디어"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            timeout=60,
        )

        return response.choices[0].message.content
    
    def _build_cartoon_prompt_from_analysis(self, image_description: str, user_text: str) -> str:
        """
        이미지 분석 결과와 사용자 텍스트로 4컷 만화 프롬프트를 구성합니다.
        
        :param image_description: GPT-4 Vision의 이미지 분석 결과
        :param user_text: 사용자가 입력한 텍스트
        :return: 완성된 프롬프트 문자열
        """
        base_prompt = f"""
        Create a 4-panel comic strip in a single image based on this description: {image_description}
        
        Requirements:
        - Arrange 4 panels in a 2x2 grid layout within one image
        - Each panel should show a sequential story progression
        - Use a cute, friendly cartoon style suitable for pet-related content
        - Include speech bubbles or thought bubbles as needed
        - Make it family-friendly and heartwarming
        - Keep the characters and setting consistent with the described image
        - Use bright, cheerful colors
        """
        
        if user_text and user_text.strip():
            user_prompt = f"\n\nUser's story theme or request: {user_text}"
            return base_prompt + user_prompt
        else:
            return base_prompt + "\n\nCreate a heartwarming daily adventure story featuring the pets from the description."
    
    def estimate_cost(self) -> Dict[str, Any]:
        """
        GPT-4 Vision + DALL-E 3 조합의 이미지 생성 비용을 추정합니다. (참고용)
        
        :return: 비용 정보
        """
        # 실제 OpenAI 가격 (2024년 기준)
        pricing = {
            "gpt4_vision_cost_per_image": 0.01,  # GPT-4 Vision: ~$0.01 per image analysis
            "dalle3_cost_per_image": 0.040,  # DALL-E 3: $0.040 per 1024x1024 standard image
        }
        
        total_cost = pricing["gpt4_vision_cost_per_image"] + pricing["dalle3_cost_per_image"]
        
        return {
            "gpt4_vision_cost_usd": pricing["gpt4_vision_cost_per_image"],
            "dalle3_cost_usd": pricing["dalle3_cost_per_image"],
            "total_cost_per_generation_usd": total_cost,
            "models": "gpt-4-vision-preview + dall-e-3",
            "note": "실제 OpenAI 공식 가격 기준 (2024년)"
        }
