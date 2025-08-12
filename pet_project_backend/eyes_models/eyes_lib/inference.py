# eyes_models/eyes_lib/inference.py (수정된 최종본)
import os
import yaml
import torch
import torch.nn as nn
from torchvision import models
from .preprocess import preprocess_image_for_pytorch
import io

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
    def __init__(self):
        # 1. 현재 파일(inference.py)이 있는 .../eyes_lib/ 폴더의 절대 경로를 찾습니다.
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 2. '..'을 사용하여 한 단계 상위 폴더인 .../eyes_models/ 의 경로를 찾습니다.
        #    이것이 바로 수정된 핵심 부분입니다.
        model_base_dir = os.path.join(current_script_dir, '..')

        # 3. 이제 .../eyes_models/ 폴더를 기준으로 올바른 경로를 설정합니다.
        config_path = os.path.join(model_base_dir, 'config.yaml') # 올바른 경로: .../eyes_models/config.yaml
        model_path = os.path.join(model_base_dir, 'saved_models', 'best_pretrained_efficientNetb0.pth')

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self.class_names = config['class_names']
        self.num_classes = len(self.class_names)
        self.threshold = config.get('threshold', 0.5)

        self.model = get_model(self.num_classes)
        
        self.model.load_state_dict(torch.load(model_path, map_location=torch.device('cpu')))

        print(f"Eye disease model weights loaded successfully from {model_path}")
        self.model.eval()

    def predict(self, image_bytes):
        if self.model is None:
            raise RuntimeError("Model is not loaded. Check initialization.")
            
        image_tensor = preprocess_image_for_pytorch(io.BytesIO(image_bytes))
        
        with torch.no_grad():
            outputs = self.model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            top_prob, top_idx = torch.max(probabilities, 1)
            
            predicted_idx = top_idx.item()
            predicted_class_name = self.class_names[predicted_idx]
            probability = top_prob.item()
            
            if probability < self.threshold:
                final_disease_name = '정상'
            else:
                final_disease_name = predicted_class_name

            all_predictions = {name: prob.item() for name, prob in zip(self.class_names, probabilities[0])}

            return final_disease_name, probability, all_predictions