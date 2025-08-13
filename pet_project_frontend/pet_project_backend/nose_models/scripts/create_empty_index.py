# nose_models/scripts/create_empty_index.py

import faiss
import numpy as np
import os

def create_empty_faiss_index():
    """
    기존 Faiss 인덱스를 덮어쓰고, 벡터가 0개인 새로운 인덱스 파일을 생성합니다.
    테스트 환경을 깨끗하게 초기화하기 위해 사용합니다.
    """
    try:
        # --- 설정 ---
        # 이 값은 config.yaml의 model.feature_dim과 일치해야 합니다.
        vector_dimension = 512
        
        # 인덱스 파일을 저장할 경로를 설정합니다.
        # 이 스크립트는 scripts 폴더에 있으므로, 상위 폴더로 이동하여 경로를 구성합니다.
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_dir = os.path.join(base_dir, 'faiss_index')
        index_path = os.path.join(index_dir, 'nose_prints.index')

        # 저장할 디렉터리가 없으면 생성합니다.
        os.makedirs(index_dir, exist_ok=True)

        # 1. 비어있는 L2 거리 기반의 Faiss 인덱스를 생성합니다.
        print(f"차원(Dimension)이 {vector_dimension}인 비어있는 Faiss 인덱스를 생성합니다.")
        # IndexFlatL2는 가장 기본적인 형태의 인덱스입니다.
        empty_index = faiss.IndexFlatL2(vector_dimension)

        # 2. 생성된 비어있는 인덱스를 파일로 저장합니다.
        print(f"'{index_path}' 경로에 인덱스를 저장합니다...")
        faiss.write_index(empty_index, index_path)

        # 3. 확인 작업
        # 저장된 파일을 다시 불러와서 벡터 개수를 확인합니다.
        reloaded_index = faiss.read_index(index_path)
        print(f"성공적으로 인덱스 파일을 생성했습니다. 등록된 벡터 수: {reloaded_index.ntotal}")

    except Exception as e:
        print(f"인덱스 생성 중 오류 발생: {e}")

if __name__ == '__main__':
    create_empty_faiss_index()
