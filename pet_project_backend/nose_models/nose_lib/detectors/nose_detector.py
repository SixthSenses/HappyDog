# nose_models/nose_lib/detectors/nose_detector.py

import cv2
import torch
import numpy as np
from PIL import Image
from typing import Tuple

class NoseDetector:
    """YOLOv5 모델을 사용하여 이미지에서 코를 탐지합니다."""

    def __init__(self, weights_path: str):
        """
        클래스 초기화 시 지정된 가중치 파일로 YOLOv5 모델을 로드합니다.
        
        :param weights_path: 학습된 YOLOv5 모델(.pt) 파일 경로
        """
        try:
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=weights_path, force_reload=True)
            print("YOLOv5 코 탐지 모델 로딩 성공")
        except Exception as e:
            print(f"YOLOv5 모델 로딩 실패: {e}")
            self.model = None

    def _detect_from_array(self, image_np: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        [핵심 로직] NumPy 배열에서 코를 탐지하고, 성공 여부와 함께 이미지를 반환합니다.
        
        :param image_np: RGB 순서의 NumPy 이미지 배열
        :return: (처리된 이미지 배열, 탐지 성공 여부) 튜플
        """
        if not self.model:
            raise RuntimeError("YOLOv5 모델이 초기화되지 않았습니다.")
        
        # YOLOv5는 BGR 순서를 선호하므로 변환합니다.
        image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
        results = self.model(image_bgr)
        detections = results.xyxy[0]

        if len(detections) > 0:
            # 가장 신뢰도가 높은 객체를 선택합니다.
            best_detection = max(detections, key=lambda x: x[4])
            x1, y1, x2, y2, _, _ = best_detection
            
            # 원본 NumPy 배열(RGB)에서 코 부분을 잘라냅니다.
            cropped_nose = image_np[int(y1):int(y2), int(x1):int(x2)]
            return cropped_nose, True # 성공 시: 잘라낸 이미지와 True 반환
        else:
            return image_np, False # 실패 시: 원본 이미지와 False 반환

    def detect_from_array(self, image_np: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        [Public] 메모리의 이미지 배열에서 코를 탐지합니다. 파이프라인에서 사용합니다.
        
        :param image_np: RGB 순서의 NumPy 이미지 배열
        :return: (처리된 이미지 배열, 탐지 성공 여부) 튜플
        """
        try:
            return self._detect_from_array(image_np)
        except Exception as e:
            print(f"배열 처리 중 오류 발생: {e}")
            # 오류 발생 시에도 파이프라인이 계속 진행되도록 원본 이미지를 반환합니다.
            return image_np, False
