
    
    ```
    공통(CPU)
    cd c:경로\HappyDog\pet_project_backend
    conda env create -f environment.yml
    conda activate happydog-backend
    pip install -e eyes_models
    pip install -e nose_models
    python run.py
    ```

    Windows CPU
    ```
    cd c:경로\HappyDog\pet_project_backend
    conda env create -f envs\environment.win-cpu.yml
    conda activate happydog-win-cpu
    pip install -e eyes_models
    pip install -e nose_models
    python run.py
    ```
    Windows CUDA 11.8
    ```
    cd c:경로\HappyDog\pet_project_backend
    conda env create -f envs\environment.win-cuda118.yml
    conda activate happydog-win-cuda118
    pip install -e eyes_models
    pip install -e nose_models
    python run.py
    ```
    macOS CPU
    ```
    cd pet_project_backend
    conda env create -f envs/environment.mac-cpu.yml
    conda activate happydog-mac-cpu
    pip install -e eyes_models
    pip install -e nose_models
    python run.py
    ```

        추가: OS/옵션별 환경 파일

        - Windows
            - CPU 전용: `envs/environment.win-cpu.yml`
            - CUDA 11.8: `envs/environment.win-cuda118.yml`

            ```bash
            conda env create -f envs/environment.win-cpu.yml
            conda activate happydog-win-cpu

            conda env create -f envs/environment.win-cuda118.yml
            conda activate happydog-win-cuda118
            ```

        - macOS
            - CPU 전용: `envs/environment.mac-cpu.yml`

            ```bash
            conda env create -f envs/environment.mac-cpu.yml
            conda activate happydog-mac-cpu
            ```

3.  **가상환경 활성화**

    ```bash
    # 공통 CPU 환경
    conda activate happydog-backend
    ```

3-1. **로컬 패키지 설치 (개발 편의용)**

```bash
# pet_project_backend에서 실행
pip install -e eyes_models
pip install -e nose_models
```

##### **2.3. 비밀 파일 설정 (`.env` 및 `secrets`)**

Git으로 공유되지 않는 민감한 파일들은 아래의 안내에 따라 설정해야 합니다.

1.  **.env 파일 생성**
    프로젝트 최상위 폴더의 `.env.example` 파일을 복사하여 `.env` 파일을 새로 만듭니다.

2.  **secrets 폴더 내 키 파일 배치**
      * `your-dev-firebase-key.json` (개발용 Firebase 키) 
      * `your-test-firebase-key.json` (테스트용 Firebase 키)
      * `your_google_client_secret.json` (Google OAuth용 클라이언트 키)

    전달받은 파일들을 `pet_project_backend/secrets/` 폴더 안에 저장합니다. `.env` 파일에 작성된 경로와 파일명이 일치해야 합니다.

-----

#### **3. 의존성 관리: 라이브러리 추가 및 공유**

#### **3-1. 실행 방법**

- 항상 `pet_project_backend` 폴더에서 실행하는 것을 권장합니다.

```bash
# Windows(cmd)
cd pet_project_backend
python run.py

# macOS(zsh/bash)
cd pet_project_backend
python run.py
```

환경 변수는 `pet_project_backend/.env`에서 로드됩니다.

#### **3-2. 모델/시크릿 파일 배치 (중요)**

- 구글 드라이브(안구 모델, 코 모델, secrets 압축):
    https://drive.google.com/drive/folders/1t-cbq0UBkc5tzTF7ATfKGuoRL6yoqNUh?usp=drive_link

- 압축 해제 후 배치 위치 예시:
    - 시크릿 키들: `pet_project_backend/secrets/`
        - 예: `happydog-***.json`, `happydog-test-***.json`, Google OAuth client secret 등
    - 안구/코 모델 가중치 및 인덱스:
        - 눈(eyes): `pet_project_backend/eyes_models/saved_models/`
        - 코(nose): `pet_project_backend/nose_models/saved_models/`, `pet_project_backend/nose_models/faiss_index/`

- `.env` 파일의 관련 항목이 실제 경로와 이름을 정확히 가리키는지 확인하세요.
    - 예: `DEV_FIREBASE_CREDENTIALS_PATH`, `TEST_FIREBASE_CREDENTIALS_PATH`,
                `YOLO_WEIGHTS_PATH`, `ML_CONFIG_PATH`, `EXTRACTOR_WEIGHTS_PATH`, `FAISS_INDEX_PATH`

개발 중 새로운 라이브러리를 설치한 경우, 반드시 다음 절차를 따라 팀원 전체에 공유해야 합니다.

1.  **라이브러리 설치:** 현재 활성화된 가상환경에 필요한 라이브러리를 설치합니다.

    ```bash
    conda install -c conda-forge <package_name>   # 권장
    conda install <package_name>
    # conda에 없을 때만 pip 사용
    pip install <package_name>
    ```

2.  **environment.yml 파일 업데이트:** 아래 명령어를 실행하여 현재 환경의 패키지 목록을 `environment.yml` 파일에 덮어씁니다.


    ```bash
    # 공통 CPU 환경 갱신 시
    conda env export --no-builds -n happydog-backend > environment.yml

    # OS/옵션별 환경은 각 환경명으로 별도 export 권장 (잠금 파일 용도)
    conda env export --no-builds -n happydog-win-cuda118 > envs/environment.win-cuda118.lock.yml
    ```

3.  **커밋 및 푸시:** 변경된 `environment.yml` 파일을 커밋하고 푸시하여 팀원들에게 공유합니다. 다른 팀원들은 `conda env update --file environment.yml --prune` 명령으로 자신의 환경을 업데이트할 수 있습니다.

-----

#### **6. 결론 요약**

1) run.py 실행 위치: `pet_project_backend` 폴더에서 실행
2) Conda 설치 위치: `pet_project_backend`에서 `-f environment.yml` (또는 `envs/...`) 실행 권장
3) 의존성 안정화:
    - CPU/CUDA, OS별 환경 파일 분리
    - OpenCV/FAISS는 conda 또는 pip 중 하나로만 사용 (혼용 금지)
    - 핵심 스택만 버전 핀: Python 3.10, PyTorch 2.5.x, numpy 1.26, pandas 2.3 등





