-----
## ** 주의 사항 **
* ** 경로 문제가 생겨서 AI한테 물어보면 대부분 sys.path.append())를 추가해서 경로를 맞출것입니다. 하지만 이건 임시방편일 뿐, 근본적인 해결책이 아닙니다. 그러니 테스트 코드 빼고는 지양합시다.
* ** Flask 실행환경은 .env에서 관리합니다. development or testing
* ** master에 merge하는 경우는 무조건 실제 api를 연결해서 테스트한 자료가 있어야 합니다..
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





