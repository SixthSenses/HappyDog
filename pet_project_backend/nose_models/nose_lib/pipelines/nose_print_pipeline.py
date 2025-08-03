# nose_models/nose_lib/pipelines/nose_print_pipeline.py

import io
import numpy as np
import faiss
from PIL import Image
from typing import Dict, Any
from nose_lib.detectors.nose_detector import NoseDetector
from nose_lib.extractors.extractor import NosePrintExtractor

class NosePrintPipeline:
    """비문 이미지 처리를 위한 End-to-end 파이프라인"""

    def __init__(self, yolo_weights_path: str, config_path: str, extractor_weights_path: str, faiss_index_path: str):
        """
        파이프라인에 필요한 모든 모델과 설정을 초기화합니다.
        """
        print("NosePrintPipeline: 초기화를 시작합니다...")
        self.duplicate_threshold = 0.7
        self.outlier_threshold = 1.2

        try:
            self.detector = NoseDetector(weights_path=yolo_weights_path)
            self.extractor = NosePrintExtractor(config_path=config_path, weights_path=extractor_weights_path)
            self.faiss_index = faiss.read_index(faiss_index_path)
            print(f"NosePrintPipeline: Faiss 인덱스 로딩 성공. 총 {self.faiss_index.ntotal}개의 벡터가 등록되어 있습니다.")
            print("NosePrintPipeline: 초기화 완료.")
        except Exception as e:
            print(f"NosePrintPipeline: 초기화 중 심각한 오류 발생: {e}")
            raise

    def process_image(self, image_bytes: bytes) -> Dict[str, Any]:
        """
        이미지 바이트를 받아 분석 결과를 반환합니다.
        
        :param image_bytes: 이미지 파일의 raw bytes
        :return: 분석 결과 딕셔너리
        """
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            image_np = np.array(image)

            image_to_process, detection_succeeded = self.detector.detect_from_array(image_np)

            if detection_succeeded:
                print("NosePrintPipeline: YOLO 코 탐지 성공.")
            else:
                print("NosePrintPipeline: YOLO 코 탐지 실패. 원본 이미지로 벡터 추출을 진행합니다.")

            vector = self.extractor.extract_vector(image_to_process)
            vector_to_search = np.array([vector], dtype='float32')
            
            # [수정됨] 첫 등록 시나리오 처리
            # 만약 인덱스가 비어있다면, 비교할 대상이 없으므로 무조건 성공으로 처리합니다.
            if self.faiss_index.ntotal == 0:
                print("NosePrintPipeline: 인덱스가 비어있어 첫 등록으로 처리합니다.")
                return {
                    "status": "SUCCESS", 
                    "vector": vector, 
                    "faiss_id": 0, # 첫 번째 등록이므로 ID는 0
                    "distance": -1.0 # 거리는 의미 없으므로 -1.0과 같은 특정 값으로 설정
                }

            # Faiss 검색 (인덱스에 데이터가 있을 경우에만 실행)
            distances, indices = self.faiss_index.search(vector_to_search, k=1)
            distance = float(distances[0][0])
            nearest_id = int(indices[0][0])
            print(f"NosePrintPipeline: Faiss 검색 완료. 가장 가까운 벡터 ID: {nearest_id}, 거리: {distance:.4f}")

            # 결과 판정
            if distance <= self.duplicate_threshold:
                return {"status": "DUPLICATE", "distance": distance, "id": nearest_id}
            elif distance > self.outlier_threshold:
                return {"status": "INVALID_IMAGE", "message": "정상적인 비문으로 보이지 않습니다.", "distance": distance}
            else:
                new_faiss_id = self.faiss_index.ntotal
                return {"status": "SUCCESS", "vector": vector, "faiss_id": new_faiss_id, "distance": distance}

        except Exception as e:
            print(f"NosePrintPipeline: 이미지 처리 파이프라인 중 오류 발생: {e}")
            return {"status": "ERROR", "message": "이미지 처리 중 서버 오류가 발생했습니다."}
