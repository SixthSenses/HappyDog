

```bash
# Anaconda 환경 활성화
conda activate pet-backend

# OpenAI 패키지 설치
pip install openai==1.8.0
```

## **환경 변수 설정**

`.env` 파일에 OpenAI API 키를 추가하세요:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## **API 사용법**

### **만화 생성 요청**

```http
POST /api/cartoon-jobs
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "file_paths": ["https://storage.googleapis.com/your-bucket/image.jpg"],
  "user_text": "우리 강아지의 하루 일상을 재미있게 표현해주세요"
}
```

### **응답**

```json
{
  "job_id": "uuid-string",
  "user_id": "user-id",
  "status": "processing",
  "original_image_url": "https://...",
  "user_text": "우리 강아지의...",
  "created_at": "2024-08-17T...",
  "updated_at": "2024-08-17T..."
}
```

### **작업 상태 확인**

```http
GET /api/cartoon-jobs/{job_id}
Authorization: Bearer {jwt_token}
```

##  **처리 흐름**

1. **사용자 요청** → API 호출
2. **즉시 응답** → 202 Accepted + job_id
3. **백그라운드 처리**:
   - GPT-4 Vision으로 이미지 분석
   - DALL-E 3로 4컷 만화 생성
   - Firebase Storage에 저장
   - 게시물 자동 생성
   - 사용자에게 알림 발송

## **비용**

- **GPT-4 Vision**: ~$0.01 per image analysis
- **DALL-E 3**: $0.040 per 1024x1024 standard image
- **총 비용**: ~$0.05 per cartoon generation

## **모니터링**

애플리케이션 로그에서 다음을 확인할 수 있습니다:

- 만화 생성 시작/완료 로그
- OpenAI API 호출 결과
- 에러 발생 시 상세 정보

### **주요 파일들**

- `app/services/openai_service.py` - OpenAI 연동 서비스
- `app/api/cartoon_jobs/routes.py` - Threading 기반 비동기 처리
- `app/api/cartoon_jobs/services.py` - 작업 관리 및 게시물 자동 생성


### **주의사항**

- 서버 재시작 시 진행 중인 작업은 상실됨
- 높은 동시 요청 시 메모리 사용량 증가
- 프로덕션 환경에서는 추후 Cloud Function으로 마이그레이션 고려

## **다음 단계**

1. OpenAI API 키 발급 및 설정
2. 실제 이미지로 테스트
3. 프롬프트 최적화
4. 에러 처리 개선
5. 프로덕션 배포 시 확장성 검토
