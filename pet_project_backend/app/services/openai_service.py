# app/services/openai_service.py
import logging
import os
from typing import Optional, Dict, Any
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
    
    def generate_cartoon(self, image_url: str, user_text: str) -> Dict[str, Any]:
        """
        사용자가 업로드한 이미지와 텍스트를 기반으로 4컷 만화를 생성합니다.
        GPT-4 Vision으로 이미지를 분석한 후 DALL-E 3로 만화를 생성합니다.
        
        :param image_url: 사용자가 업로드한 원본 이미지 URL
        :param user_text: 사용자가 입력한 텍스트
        :return: 생성된 이미지 정보를 담은 딕셔너리
        """
        if not self.client:
            raise RuntimeError("OpenAIService가 초기화되지 않았습니다. init_app을 먼저 호출해주세요.")
        
        try:
            # 1단계: GPT-4 Vision으로 이미지 분석
            image_description = self._analyze_image_with_gpt4_vision(image_url)
            
            # 2단계: 분석 결과와 사용자 텍스트로 만화 프롬프트 구성
            cartoon_prompt = self._build_cartoon_prompt_from_analysis(image_description, user_text)
            
            # 3단계: DALL-E 3로 4컷 만화 생성
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=cartoon_prompt,
                size="1024x1024",  # 표준 크기
                quality="standard",  # 표준 품질 (저비용)
                n=1  # 이미지 1장 생성
            )
            
            # 생성된 이미지 정보 반환
            generated_image = response.data[0]
            
            return {
                "success": True,
                "image_url": generated_image.url,
                "image_description": image_description,
                "final_prompt": cartoon_prompt,
                "revised_prompt": getattr(generated_image, 'revised_prompt', cartoon_prompt),
                "model_used": "gpt-4-vision + dall-e-3"
            }
            
        except Exception as e:
            logging.error(f"OpenAI 만화 생성 실패: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _analyze_image_with_gpt4_vision(self, image_url: str) -> str:
        """
        GPT-4o를 사용하여 이미지를 분석하고 설명을 생성합니다.
        
        :param image_url: 분석할 이미지 URL
        :return: 이미지 분석 결과 텍스트
        """
        try:
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
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logging.error(f"GPT-4 Vision 이미지 분석 실패: {e}", exc_info=True)
            # 분석 실패 시 기본 설명 반환
            return "귀여운 반려동물이 있는 일상적인 장면"
    
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
