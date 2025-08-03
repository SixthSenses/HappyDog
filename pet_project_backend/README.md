### **Pet Project Backend: 가이드**

#### **1. 프로젝트 개요 및 아키텍처**

본 문서는 "Pet Project Backend"의 시스템 아키텍처, 설계 원칙, 그리고 표준 개발 워크플로우를 정의하는 기술 가이드입니다.

본 프로젝트는 Python Flask를 기반으로 하며, 애플리케이션 팩토리(Application Factory) 패턴과 \*\*블루프린트(Blueprint)\*\*를 활용하여 기능별 모듈화를 지향합니다. 핵심 설계 철학은 \*\*'관심사의 분리(Separation of Concerns)'\*\*로, 모든 코드는 명확한 역할과 책임을 가지는 계층으로 분리됩니다.
-----
## ** 주의 사항 **
* ** 경로 문제가 생겨서 AI한테 물어보면 대부분 sys.path.append())를 추가해서 경로를 맞출것입니다. 하지만 이건 임시방편일 뿐, 근본적인 해결책이 아닙니다. 그러니 테스트 코드 빼고는 지양합시다.
* ** Flask 실행환경은 .env에서 관리합니다. development or testing
* ** master에 merge하는 경우는 무조건 실제 api를 연결해서 테스트한 자료가 있어야 합니다.
-----

#### **2. 로컬 개발 환경 설정**

##### **2.1. 사전 준비**

  * Git
  * Anaconda or Miniconda

##### **2.2. 초기 설정 절차**

1.  **리포지토리 복제 (Clone)**

    ```bash
    git clone <repository_url>
    cd pet_project_backend
    ```

2.  **Conda 가상환경 생성**

      * ⚠️ **중요: `environment.yml` 파일 수정**
        `conda env create` 명령어를 실행하기 전, 반드시 `environment.yml` 파일을 텍스트 편집기로 열어 맨 아래에 있는 `prefix:` 로 시작하는 줄을 찾아 **삭제**해주세요. 이 줄은 환경을 생성한 사람의 개인 컴퓨터 경로이므로, 삭제해야만 각 팀원의 환경에 맞게 설치됩니다.

    <!-- end list -->

    ```bash
    conda env create -f environment.yml
    ```

3.  **가상환경 활성화**

    ```bash
    conda activate pet_project_backend
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

개발 중 새로운 라이브러리를 설치한 경우, 반드시 다음 절차를 따라 팀원 전체에 공유해야 합니다.

1.  **라이브러리 설치:** 현재 활성화된 가상환경에 필요한 라이브러리를 설치합니다.

    ```bash
    conda install -c conda-forge <package_name>  최우선
    conda install <package_name> 우선
    # 또는 pip install <package_name> 쩔수
    ```

2.  **environment.yml 파일 업데이트:** 아래 명령어를 실행하여 현재 환경의 패키지 목록을 `environment.yml` 파일에 덮어씁니다.


    ```bash
    conda env export --no-builds > environment.yml
    ```

3.  **커밋 및 푸시:** 변경된 `environment.yml` 파일을 커밋하고 푸시하여 팀원들에게 공유합니다. 다른 팀원들은 `conda env update --file environment.yml --prune` 명령으로 자신의 환경을 업데이트할 수 있습니다.

-----

#### ** 프로젝트 구조 해설 **



---
## 1. 프로젝트 최상위 구조 (`pet_project_backend/`)

프로젝트의 가장 바깥 단계로, 애플리케이션 코드, 머신러닝 모델, 설정 파일 등을 포함합니다.

* **`.vscode/`**: Visual Studio Code 편집기 관련 설정 파일이 저장되는 폴더입니다. `launch.json`은 디버깅 실행 설정을 담고 있습니다.
* **`action_models/`, `eye_models/`**: (향후 확장용) 행동 분석, 안구 질환 등 각기 다른 머신러닝 모델을 독립적으로 개발하기 위한 프로젝트 폴더입니다.
* **`nose_models/`**: **비문 인식 머신러닝 프로젝트**가 담긴 핵심 폴더입니다. Flask 앱과 분리되어 독립적으로 개발 및 테스트가 가능합니다. (상세 설명은 3번 항목 참조)
* **`app/`**: **Flask 애플리케이션**의 모든 코드가 들어있는 핵심 폴더입니다. (상세 설명은 2번 항목 참조)
* **`secrets/`**: Firebase 인증 키(`.json`), Google Client Secret 등 민감한 정보를 담은 파일을 보관하는 폴더입니다. 이 폴더는 **`.gitignore`에 반드시 포함**하여 Git에 올라가지 않도록 해야 합니다.(귀찮아서 그냥 올려버릴려고 gitignore에서 뺀적있는데 github가 자동으로 감지해서 경고 때리더군요...
* **`uploads/`**: 사용자가 업로드한 파일이 임시로 저장될 수 있는 폴더입니다.
* **`.env`**: 데이터베이스 주소, 비밀 키 등 환경에 따라 달라지는 설정값들을 저장하는 파일입니다.
* **`.gitignore`**: Git 버전 관리에서 제외할 파일 및 폴더 목록을 정의합니다. (`.env`, `secrets/` 등이 포함됩니다.)
* **`environment.yml`**: Conda 가상환경에 필요한 패키지 목록을 정의한 파일로, 개발 환경을 통일시키는 역할을 합니다.
* **`run.py`**: Flask 애플리케이션을 실행하는 진입점(Entry Point) 파일입니다.

---
## 2. Flask 애플리케이션 구조 (`app/`)

**애플리케이션 팩토리(Application Factory)** 패턴과 **기능 중심(Feature-centric)** 구조를 따르고 있습니다.

* **`__init__.py`**: `create_app()` 함수가 위치하는 곳으로, Flask 앱 인스턴스를 생성하고, 각종 설정, 서비스, 블루프린트(API)를 초기화하고 등록하는 가장 중요한 파일입니다.
* **`core/`**: 애플리케이션의 핵심 설정과 관련된 코드를 담습니다.
    * `config.py`: `development`, `testing` 등 다양한 환경별 설정을 클래스로 정의합니다.
* **`models/`**: 데이터베이스의 데이터 구조를 정의하는 파일을 담습니다.
    * `user.py`, `pet.py`: 사용자, 반려동물 객체의 속성(예: 이름, 이메일)을 정의하는 데이터클래스(Dataclass)가 위치합니다.
* **`services/`**: 여러 기능에서 공통으로 사용될 수 있는 비즈니스 로직을 담습니다.
    * `google_auth_service.py`: Google OAuth 인증 관련 로직을 처리합니다.
    * `storage_service.py`: Firebase Storage에 파일을 업로드하는 등 스토리지 관련 로직을 처리합니다.
* **`api/`**: 실제 API 엔드포인트를 기능별로 그룹화한 폴더입니다. 각 기능 폴더는 독립적인 모듈처럼 구성됩니다.
    * **`auth/`, `mypage/`, `pets/` 등 (각 기능 폴더)**:
        * `routes.py`: Flask의 **블루프린트(Blueprint)**를 정의하고, `@bp.route(...)`를 사용하여 실제 API 경로와 HTTP 메서드(GET, POST 등)를 정의합니다. HTTP 요청과 응답을 직접 처리하는 계층입니다.
        * `services.py`: 해당 기능(예: `mypage`)에만 특화된 비즈니스 로직을 담습니다. `routes.py`는 이 서비스 클래스를 호출하여 작업을 수행합니다.
        * `schemas.py`: Marshmallow 스키마를 정의하여, API 요청 데이터의 유효성을 검사하고(역직렬화), 응답 데이터의 형식을 지정(직렬화)하는 역할을 합니다.

---
## 3. 비문 인식 모델 구조 (`nose_models/`)

Flask 앱과 완전히 분리된, 그 자체로 하나의 **설치 가능한(installable) 파이썬 패키지**입니다.

* **`setup.py`**: 이 폴더 전체를 하나의 라이브러리처럼 `pip install -e .` 명령어로 설치할 수 있게 해주는 설정 파일입니다. 이를 통해 Flask 앱에서 `from nose_lib import ...` 와 같이 깔끔하게 코드를 불러올 수 있습니다.
* **`config.yaml`**: 모델의 구조, 학습 파라미터, 이미지 크기 등 머신러닝 실험에 필요한 모든 설정값을 코드와 분리하여 관리합니다.
* **`nose_lib/`**: 모델의 핵심 파이썬 소스 코드가 위치하는 패키지입니다.
    * `detectors/`: YOLOv5 모델을 사용하여 이미지에서 코를 탐지하는 `NoseDetector` 클래스가 있습니다.
    * `extractors/`: 탐지된 코 이미지에서 특징 벡터(vector)를 추출하는 `NosePrintExtractor` 클래스가 있습니다.
    * `backbone/`: 특징 추출 모델의 기반이 되는 CNN 아키텍처(예: `SEResNeXt_IBN`) 코드가 있습니다. `backbone_build.py`는 설정에 따라 원하는 모델을 생성하는 팩토리 역할을 합니다.
    * `pipelines/`: `NoseDetector`와 `NosePrintExtractor`를 순서대로 실행하여 이미지 한 장으로 최종 결과를 도출하는 `NosePrintPipeline` 클래스가 있습니다.
* **`saved_models/`**: 학습이 완료된 모델의 가중치 파일(`.pt`, `.pth`)을 저장합니다.
* **`faiss_index/`**: 등록된 모든 비문 벡터들을 검색 가능하도록 만든 Faiss 인덱스 파일(`.index`)과 초기 벡터 데이터(`.npy`)를 저장합니다.
* **`initial_dataset/`**: Faiss 인덱스를 처음 구축할 때 사용된 이미지들을 보관합니다.
* **`scripts/`**: 모델 테스트, Faiss 인덱스 구축, 벡터 추출 등 개발 과정에 필요한 각종 유틸리티 스크립트들을 모아둔 폴더입니다.
---
## 4. 안구 질환 모델 구조 (`eyes_models/`)
---
## 5. 강아지 번역기 모델 구조 (`action_models/`)
---

 * `run.py`: 애플리케이션 서버를 실행하는 유일한 진입점입니다.
    ```python
    # run.py
    from dotenv import load_dotenv
    import os
    from app import create_app
    load_dotenv()
    app = create_app()

    if __name__ == '__main__':
     host = os.getenv('FLASK_RUN_HOST', '127.0.0.1')
     port = int(os.getenv('FLASK_RUN_PORT', 5000))
     debug = app.config.get('DEBUG', False)
     app.run(host=host, port=port, debug=debug)
    ```
-----

