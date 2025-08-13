#pet_project_backend\nose_models\nose_lib\extractors\extractor.py
import yaml
import torch
import numpy as np
from PIL import Image
from typing import Dict, Any
# 'nose_lib'를 기준으로 절대 경로 임포트를 사용합니다.
from nose_lib.siamese_cosine import SiameseNetwork
from nose_lib.transforms import get_val_transform

class NosePrintExtractor:
    def __init__(self, config_path: str, weights_path: str):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            print("설정 파일(config.yaml) 로딩 성공!")
            model_config = config['model']
            model_name = model_config['name']
            in_features = model_config['in_features']
            feature_dim = model_config['feature_dim']
            self.model = SiameseNetwork(
                backbone_name=model_name,
                in_features=in_features,
                feature_dim=feature_dim,
                pretrained=False
            )
            print(f"'{model_name}' 모델 생성 성공!")
            checkpoint = torch.load(weights_path, map_location=torch.device('cpu'), weights_only=False)

                # 2. 그 안에서 '부품 상자'(model_state_dict)만 꺼냅니다.
            state_dict = checkpoint['model_state_dict']

            self.model.load_state_dict(state_dict)
            print(f"'{weights_path}' 에서 모델 가중치 로딩 성공!")
            self.model.eval()
            dataset_config = config['dataset']
            image_size = dataset_config['image_size']
            use_clahe_sharpen = dataset_config['use_clahe_sharpen']
            self.transform = get_val_transform(
                img_height=image_size,
                img_width=image_size,
                use_clahe_sharpen=use_clahe_sharpen
            )
            print("추론용 이미지 전처리 파이프라인 생성 완료!")
        except FileNotFoundError as e:
            print(f"오류: 설정 또는 가중치 파일을 찾을 수 없습니다. 경로를 확인하세요: {e}")
            raise
        except Exception as e:
            print(f"모델 초기화 중 예상치 못한 오류 발생: {e}")
            raise

    def extract_vector(self, image_np: np.ndarray) -> np.ndarray:
        try:
            with torch.no_grad():
                image_pil = Image.fromarray(image_np)
                image_tensor = self.transform(image_pil)
                image_tensor = image_tensor.unsqueeze(0)
                vector_tensor = self.model.extract(image_tensor)
                vector_np = vector_tensor.cpu().numpy()[0]
                return vector_np
        except Exception as e:
            print(f"벡터 추출 중 오류 발생: {e}")
            raise