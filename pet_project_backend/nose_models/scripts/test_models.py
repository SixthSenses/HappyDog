# --- nose_models/scripts/test_models.py ---

import os
from PIL import Image
import numpy as np

# nose_lib 패키지가 설치되었으므로, sys.path 조작 없이 바로 절대 경로로 임포트합니다.
from nose_lib.detectors.nose_detector import NoseDetector
from nose_lib.extractors.extractor import NosePrintExtractor
from nose_lib.pipelines.nose_print_pipeline import NosePrintPipeline

def test_detector(base_dir: str):
    """NoseDetector 클래스를 테스트합니다."""
    print("\n--- 1. NoseDetector 테스트 시작 ---")
    weights_path = os.path.join(base_dir, 'saved_models', 'nose_segment', 'best.pt')
    # 이미지 경로는 initial_dataset이 아닌 scripts 폴더 바로 아래에 있다고 가정합니다.
    # 만약 initial_dataset에 있다면 경로를 수정해주세요.
    image_path = os.path.join(base_dir, 'scripts', 'golden-retriever-puppy-3783517_640.jpg')
    output_dir = os.path.join(base_dir, 'scripts', 'test_outputs')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'cropped_nose.jpg')

    if not os.path.exists(image_path):
        print(f"경고: 테스트 이미지를 찾을 수 없어 Detector 테스트를 건너뜁니다: {image_path}")
        return

    detector = NoseDetector(weights_path=weights_path)
    image_np = np.array(Image.open(image_path).convert('RGB'))
    
    # [수정됨] NumPy 배열을 직접 처리하는 detect_from_array 메서드를 호출합니다.
    cropped_image_array = detector.detect_from_array(image_np)

    if cropped_image_array is not None and cropped_image_array.size > 0:
        print(" 코 탐지 성공!")
        result_image = Image.fromarray(cropped_image_array)
        result_image.save(output_path)
        print(f"-> 잘라낸 이미지를 '{output_path}' 에 저장했습니다.")
    else:
        print("코 탐지 실패: 이미지에서 코를 찾지 못했습니다.")

def test_extractor(base_dir: str):
    """NosePrintExtractor 클래스를 테스트합니다."""
    print("\n--- 2. NosePrintExtractor 테스트 시작 ---")
    config_path = os.path.join(base_dir, 'config.yaml')
    weights_path = os.path.join(base_dir, 'saved_models', 'nose_print', 'seresnext50_ibn_custom_best_model.pth')
    image_path = os.path.join(base_dir, 'scripts', 'test_outputs', 'cropped_nose.jpg') # 코만 있는 이미지 또는 일반 이미지

    if not os.path.exists(image_path):
        print(f"경고: 테스트 이미지를 찾을 수 없어 Extractor 테스트를 건너뜁니다: {image_path}")
        return

    extractor = NosePrintExtractor(config_path=config_path, weights_path=weights_path)
    image_np = np.array(Image.open(image_path).convert('RGB'))
    vector = extractor.extract_vector(image_np)

    if vector is not None:
        print("벡터 추출 성공!")
        print(f"-> 추출된 벡터의 차원: {vector.shape}")
        print(f"-> 벡터 앞 5개 값: {vector[:5]}")
    else:
        print(" 벡터 추출 실패.")

def test_pipeline(base_dir: str):
    """NosePrintPipeline 클래스를 테스트합니다."""
    print("\n--- 3. NosePrintPipeline 테스트 시작 ---")
    image_path = os.path.join(base_dir, 'scripts', 'golden-retriever-puppy-3783517_640.jpg')

    if not os.path.exists(image_path):
        print(f"경고: 테스트 이미지를 찾을 수 없어 Pipeline 테스트를 건너뜁니다: {image_path}")
        return

    try:
        # [수정됨] 파이프라인 초기화에 필요한 모든 경로를 인자로 전달합니다.
        yolo_weights = os.path.join(base_dir, 'saved_models', 'nose_segment', 'best.pt')
        config_path = os.path.join(base_dir, 'config.yaml')
        extractor_weights = os.path.join(base_dir, 'saved_models', 'nose_print', 'seresnext50_ibn_custom_best_model.pth')
        faiss_path = os.path.join(base_dir, 'faiss_index', 'nose_prints.index')

        pipeline = NosePrintPipeline(
            yolo_weights_path=yolo_weights,
            config_path=config_path,
            extractor_weights_path=extractor_weights,
            faiss_index_path=faiss_path
        )
        
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        result = pipeline.process_image(image_bytes)
        print("파이프라인 실행 성공!")
        print(f"-> 최종 결과: {result}")
    except Exception as e:
        print(f"파이프라인 테스트 중 오류 발생: {e}")

# --- 실행 시작점 ---
if __name__ == '__main__':
    # 이 스크립트 파일의 위치를 기준으로 상위 폴더(nose_models)의 경로를 찾습니다.
    main_base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # [수정됨] 정의된 테스트 함수들을 순서대로 호출합니다.
    test_detector(main_base_dir)
    test_extractor(main_base_dir)
    test_pipeline(main_base_dir)