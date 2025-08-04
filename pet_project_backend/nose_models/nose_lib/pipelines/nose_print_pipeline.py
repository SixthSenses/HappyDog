# nose_models/nose_lib/pipelines/nose_print_pipeline.py
import cv2
import io
import numpy as np
import faiss
from PIL import Image
from typing import Dict, Any

from pet_project_backend.app.services.storage_service import StorageService
from nose_lib.detectors.nose_detector import NoseDetector
from nose_lib.extractors.extractor import NosePrintExtractor

class NosePrintPipeline:
    """비문 이미지 처리를 위한 End-to-end 파이프라인"""

    def __init__(self, yolo_weights_path: str, config_path: str, extractor_weights_path: str, faiss_index_path: str):
        print("NosePrintPipeline: 초기화를 시작합니다...")
        self.duplicate_threshold = 0.7
        self.outlier_threshold = 1.2
        
        # [수정됨] 나중에 인덱스 파일을 저장하기 위해 경로를 인스턴스 변수로 저장합니다.
        self.faiss_index_path = faiss_index_path

        try:
            self.detector = NoseDetector(weights_path=yolo_weights_path)
            self.extractor = NosePrintExtractor(config_path=config_path, weights_path=extractor_weights_path)
            self.faiss_index = faiss.read_index(self.faiss_index_path)
            print(f"NosePrintPipeline: Faiss 인덱스 로딩 성공. 총 {self.faiss_index.ntotal}개의 벡터가 등록되어 있습니다.")
            print("NosePrintPipeline: 초기화 완료.")
        except Exception as e:
            print(f"NosePrintPipeline: 초기화 중 심각한 오류 발생: {e}")
            raise

    def process_image(self, storage_service: StorageService, file_path: str) -> Dict[str, Any]:
        """파일 경로를 받아 Storage에서 이미지를 다운로드한 후 분석 결과를 반환합니다."""
        try:
            # [신규] Storage에서 file_path를 이용해 이미지 바이트를 가져옵니다.
            blob = storage_service.bucket.blob(file_path)
            if not blob.exists():
                print(f"NosePrintPipeline: Storage에서 파일을 찾을 수 없음 - {file_path}")
                return {"status": "ERROR", "message": "스토리지에서 파일을 찾을 수 없습니다."}
            image_bytes = blob.download_as_bytes()
            
            # --- 여기부터는 기존 로직과 완전히 동일합니다 ---
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            image_np = np.array(image)
            resized_image_np = cv2.resize(image_np, (640, 640), interpolation=cv2.INTER_AREA)
            image_to_process, detection_succeeded = self.detector.detect_from_array(resized_image_np)

            if detection_succeeded:
                print("NosePrintPipeline: YOLO 코 탐지 성공.")
            else:
                print("NosePrintPipeline: YOLO 코 탐지 실패. 원본 이미지로 벡터 추출을 진행합니다.")

            vector = self.extractor.extract_vector(image_to_process)
            vector_to_search = np.array([vector], dtype='float32')
            
            if self.faiss_index.ntotal == 0:
                print("NosePrintPipeline: 인덱스가 비어있어 첫 등록으로 처리합니다.")
                return {"status": "SUCCESS", "vector": vector, "faiss_id": 0, "distance": -1.0}

            distances, indices = self.faiss_index.search(vector_to_search, k=1)
            distance = float(distances[0][0])
            nearest_id = int(indices[0][0])
            print(f"NosePrintPipeline: Faiss 검색 완료. 가장 가까운 벡터 ID: {nearest_id}, 거리: {distance:.4f}")

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

    def add_vector_to_index(self, vector: np.ndarray):
        """
        [신규] 새로운 벡터를 Faiss 인덱스에 추가하고 파일에 저장하여 영구적으로 반영합니다.
        
        :param vector: 인덱스에 추가할 1차원 NumPy 배열 벡터
        """
        try:
            vector_to_add = np.array([vector], dtype='float32')
            # 1. 메모리에 있는 인덱스에 벡터를 추가합니다.
            self.faiss_index.add(vector_to_add)
            
            # 2. 변경된 인덱스를 디스크에 다시 저장하여 덮어씁니다.
            # 참고: 동시성 문제가 발생할 수 있는 환경에서는 파일 락(File Lock) 등의 처리가 필요할 수 있습니다.
            faiss.write_index(self.faiss_index, self.faiss_index_path)
            print(f"NosePrintPipeline: 새 벡터를 인덱스에 추가하고 파일을 저장했습니다. 총 벡터 수: {self.faiss_index.ntotal}")
        except Exception as e:
            print(f"NosePrintPipeline: Faiss 인덱스에 벡터 추가 및 저장 중 오류 발생: {e}")
            # 실제 서비스에서는 이 경우 롤백(Rollback) 로직을 고려해야 할 수 있습니다.
            raise
