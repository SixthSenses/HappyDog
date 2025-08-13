# =====================================================================================
# --- nose_models/scripts/extract_vectors.py ---
# =====================================================================================
import os
import glob
import numpy as np
from PIL import Image
from tqdm import tqdm
from typing import List

# nose_lib 패키지가 설치되었으므로, sys.path 조작 없이 바로 절대 경로로 임포트합니다.
from nose_lib.extractors.extractor import NosePrintExtractor

def extract_all_vectors():
    """
    지정된 디렉토리의 모든 이미지에서 비문 벡터를 추출하고 .npy 파일로 저장합니다.
    """
    print("===== 비문 벡터 일괄 추출 스크립트 시작 =====")

    # --- 경로 설정 ---
    # 이 스크립트 파일의 위치를 기준으로 상위 폴더(nose_models)의 경로를 찾습니다.
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(scripts_dir) # nose_models/

    # 모든 경로는 base_dir를 기준으로 설정하여, 어디서 실행하든 경로가 깨지지 않습니다.
    CONFIG_PATH = os.path.join(base_dir, 'config.yaml')
    WEIGHTS_PATH = os.path.join(base_dir, 'saved_models', 'nose_print', 'seresnext50_ibn_custom_best_model.pth')
    IMAGE_DIR_PATH = os.path.join(base_dir, 'initial_dataset')
    OUTPUT_VECTORS_PATH = os.path.join(base_dir, 'faiss_index', 'initial_vectors.npy')

    os.makedirs(os.path.dirname(OUTPUT_VECTORS_PATH), exist_ok=True)

    # --- 파일 경로 검증 ---
    for path in [CONFIG_PATH, WEIGHTS_PATH, IMAGE_DIR_PATH]:
        if not os.path.exists(path):
            print(f"오류: 필수 경로를 찾을 수 없습니다: {path}")
            return

    try:
        # 1. NosePrintExtractor 인스턴스를 생성합니다.
        print("비문 벡터 추출기(NosePrintExtractor)를 초기화합니다...")
        extractor = NosePrintExtractor(config_path=CONFIG_PATH, weights_path=WEIGHTS_PATH)

        # 2. 이미지 파일 목록을 가져옵니다.
        image_extensions = ('*.jpg', '*.jpeg', '*.png')
        image_paths: List[str] = []
        for ext in image_extensions:
            image_paths.extend(glob.glob(os.path.join(IMAGE_DIR_PATH, ext)))
        
        if not image_paths:
            print(f"오류: '{IMAGE_DIR_PATH}' 디렉토리에서 이미지를 찾을 수 없습니다.")
            return

        print(f"총 {len(image_paths)}개의 이미지에서 벡터를 추출합니다.")

        # 3. 각 이미지에서 벡터를 추출합니다.
        all_vectors: List[np.ndarray] = []
        for image_path in tqdm(image_paths, desc="벡터 추출 진행률"):
            try:
                img = Image.open(image_path).convert('RGB')
                img_np = np.array(img)
                vector = extractor.extract_vector(img_np)
                all_vectors.append(vector)
            except Exception as e:
                print(f"\n경고: '{os.path.basename(image_path)}' 처리 중 오류 발생: {e}")

        if not all_vectors:
            print("오류: 유효한 벡터를 하나도 추출하지 못했습니다.")
            return

        # 4. 벡터 리스트를 NumPy 배열로 변환하고 저장합니다.
        vectors_array = np.array(all_vectors).astype('float32')
        np.save(OUTPUT_VECTORS_PATH, vectors_array)

        print("\n===== 벡터 추출 완료 =====")
        print(f"총 {len(vectors_array)}개의 벡터를 성공적으로 추출했습니다.")
        print(f"결과가 '{OUTPUT_VECTORS_PATH}' 파일에 저장되었습니다.")

    except Exception as e:
        print(f"\n스크립트 실행 중 심각한 오류 발생: {e}")

if __name__ == '__main__':
    extract_all_vectors()