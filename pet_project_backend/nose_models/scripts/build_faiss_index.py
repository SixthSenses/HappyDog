# =====================================================================================
# --- nose_models/scripts/build_faiss_index.py ---
# =====================================================================================
import os
import numpy as np
import faiss

def build_index():
    """
    .npy 파일에 저장된 벡터들로 Faiss 인덱스를 구축하고 .index 파일로 저장합니다.
    """
    print("===== Faiss 인덱스 구축 스크립트 시작 =====")

    # --- 경로 설정 ---
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(scripts_dir) # nose_models/

    VECTORS_PATH = os.path.join(base_dir, 'faiss_index', 'initial_vectors.npy')
    OUTPUT_INDEX_PATH = os.path.join(base_dir, 'faiss_index', 'nose_prints.index')

    if not os.path.exists(VECTORS_PATH):
        print(f"오류: 벡터 파일(.npy)을 찾을 수 없습니다: {VECTORS_PATH}")
        print("먼저 extract_vectors.py 스크립트를 실행하여 벡터를 추출해주세요.")
        return

    try:
        print(f"'{VECTORS_PATH}'에서 벡터 데이터를 로딩합니다...")
        vectors = np.load(VECTORS_PATH)

        if vectors.size == 0 or len(vectors.shape) != 2:
            print("오류: 벡터 파일이 비어있거나 형식이 잘못되었습니다. (2차원 배열이어야 함)")
            return
        
        dimension = vectors.shape[1]
        print(f"벡터 로딩 완료. 총 {vectors.shape[0]}개의 벡터, 차원: {dimension}")

        print(f"{dimension} 차원으로 Faiss 인덱스를 생성합니다...")
        index = faiss.IndexFlatL2(dimension)

        print("인덱스에 벡터를 추가합니다...")
        index.add(vectors)

        print(f"완성된 인덱스를 '{OUTPUT_INDEX_PATH}' 파일로 저장합니다...")
        faiss.write_index(index, OUTPUT_INDEX_PATH)

        print("\n===== Faiss 인덱스 구축 완료 =====")
        print(f"총 {index.ntotal}개의 벡터가 인덱스에 성공적으로 저장되었습니다.")

    except Exception as e:
        print(f"\n스크립트 실행 중 오류 발생: {e}")

if __name__ == '__main__':
    build_index()