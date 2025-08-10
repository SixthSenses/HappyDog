import os
import yaml
import torch
import torch.nn as nn
from torchvision import models
from .preprocess import preprocess_image_for_pytorch
import io # <-- io 라이브러리를 import 해야 합니다.

def get_model(num_classes):
    model = models.efficientnet_b0(weights=None)
    in_features = model.classifier[1].in_features
    model.classifier[1] = nn.Sequential(
        nn.Linear(in_features, 128),
        nn.ReLU(),
        nn.Dropout(0.4),
        nn.Linear(128, num_classes)
    )
    return model

class EyeAnalyzer:
    # /eyes_models/eyes_lib/inference.py 의 EyeAnalyzer 클래스

    def __init__(self):
        """
        [디버깅용] 모델 로딩 실패 시 즉시 에러를 발생시키도록 try...except를 제거했습니다.
        """
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        model_base_dir = os.path.join(current_script_dir, '..')

        # 실제 파일명으로 잘 수정하셨습니다. 그대로 유지하세요.
        actual_model_filename = 'best_pretrained_efficientNetb0.pth'
        config_path = os.path.join(model_base_dir, 'config.yaml')
        model_path = os.path.join(model_base_dir, 'saved_models', actual_model_filename)

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self.class_names = config['class_names']
        self.num_classes = len(self.class_names)
        self.threshold = config.get('threshold', 0.5)

        self.model = get_model(self.num_classes)

        # 여기서 문제가 발생하면, 프로그램은 즉시 멈추고 상세한 에러를 출력합니다.
        self.model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))

        print(f"✅ Eye disease model weights loaded successfully from {model_path}")
        self.model.eval()

    def predict(self, image_bytes): # <-- 인자 이름이 image_stream에서 image_bytes로 변경
        """
        [수정됨] 이미지 내용물(bytes)을 직접 받아 처리합니다.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded. Check initialization.")
            
        # [수정됨] 받은 내용물을 파일 통로(BytesIO)로 만들어서 전처리 함수에 전달합니다.
        image_tensor = preprocess_image_for_pytorch(io.BytesIO(image_bytes))
        
        with torch.no_grad():
            outputs = self.model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            top_prob, top_idx = torch.max(probabilities, 1)
            
            # --- 아래 로직이 전부 수정/추가되었습니다 ---
            
            # 1. 모델의 기본 예측 결과 확인
            predicted_idx = top_idx.item()
            predicted_class_name = self.class_names[predicted_idx]
            probability = top_prob.item()
            
            # 2. 임계값(threshold) 규칙 적용
            if probability < self.threshold:
                # 모델의 예측 확률이 임계값보다 낮으면 '정상'으로 판단
                final_disease_name = '정상'
            else:
                # 임계값보다 높으면 모델의 예측을 그대로 사용
                final_disease_name = predicted_class_name

            # 3. 모든 클래스에 대한 확률값도 함께 반환
            all_predictions = {name: prob.item() for name, prob in zip(self.class_names, probabilities[0])}

            # 최종 판단된 질환명, 그때의 확률, 그리고 모든 예측값을 반환
            return final_disease_name, probability, all_predictions