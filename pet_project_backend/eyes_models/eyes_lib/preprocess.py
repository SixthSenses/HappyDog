# eyes_models/eyes_lib/preprocess.py

import io
from PIL import Image
import torch
from torchvision import transforms

# Colab 코드에서 가져온 정확한 평균 및 표준편차 값
_mean = (0.2661731541156769, 0.21958693861961365, 0.19908438622951508)
_std = (0.2739975154399872, 0.24197140336036682, 0.23442873358726501)

def get_inference_transforms():
    """
    추론 시 사용할 Torchvision Transform을 반환합니다.
    (Colab의 valid_transform과 동일)
    """
    return transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(_mean, _std)
    ])

def preprocess_image_for_pytorch(image_stream):
    """
    이미지 스트림을 받아 PyTorch 모델 입력에 맞게 전처리합니다.
    """
    # 이미지 열기
    image = Image.open(image_stream)
    
    # RGB 채널로 통일
    if image.mode != "RGB":
        image = image.convert("RGB")
    
    # 정의된 transform 적용
    transform = get_inference_transforms()
    image_tensor = transform(image)
    
    # 배치 차원 추가: (C, H, W) -> (1, C, H, W)
    return image_tensor.unsqueeze(0)