# 강아지 비문(Nose Print) 모델 - FAISS 로직 및 임계값 분석

**분석일**: 2025-10-12  
**분석 대상**: HappyDog 비문 인식 시스템  
**모델**: Siamese Network (SE-ResNeXt50 IBN Custom)

---

## 🎯 전체 시스템 개요

### 시스템 구조
```
이미지 입력
    ↓
[YOLO 코 탐지] → 코 영역 추출
    ↓
[Siamese Network] → 512차원 특징 벡터 추출 (L2 정규화)
    ↓
[FAISS IndexFlatL2] → 최근접 이웃 검색 (L2 거리)
    ↓
[임계값 판단] → DUPLICATE / SUCCESS / INVALID_IMAGE
```

---

## 📊 모델 학습 방식 분석

### 1. **Siamese Network with Cosine Similarity**

**파일**: `nose_lib/siamese_cosine.py`

#### 학습 구조
```python
class SiameseNetwork(nn.Module):
    def extract(self, x: torch.Tensor, normalize: bool = True) -> torch.Tensor:
        x = self.backbone(x)
        x = self.projector(x)
        return F.normalize(x, dim=1) if normalize else x  # ← L2 정규화!
```

**핵심 포인트:**
- ✅ **L2 정규화된 벡터 추출**: `F.normalize(x, dim=1)`
- ✅ **벡터 차원**: 512차원 (`feature_dim: 512`)
- ✅ **Backbone**: SE-ResNeXt50 with IBN (Instance-Batch Normalization)

#### 학습 방식 (추정)
```
입력: (image1, image2, label)
- label = 1: 같은 개체 (positive pair)
- label = 0: 다른 개체 (negative pair)

손실 함수: Contrastive Loss or Triplet Loss
- margin = 0.6 (config.yaml)
- 목표: 같은 nose는 가깝게, 다른 nose는 멀리
```

**학습 목표:**
- **Positive pair** (label=1): cosine similarity ↑ (거리 ↓)
- **Negative pair** (label=0): cosine similarity ↓ (거리 ↑)

---

## 🔍 FAISS 인덱스 구조

### 1. **인덱스 타입**: `IndexFlatL2`

**파일**: `scripts/build_faiss_index.py`

```python
index = faiss.IndexFlatL2(dimension)  # dimension = 512
```

**특징:**
- **거리 메트릭**: L2 거리 (Euclidean Distance)
- **검색 방식**: Brute-force (전수 조사)
- **정확도**: 100% (근사치 아님)

### 2. **L2 거리 vs Cosine 유사도**

#### L2 정규화 벡터의 L2 거리 관계
벡터가 L2 정규화되어 있을 때 (||v|| = 1):

```
L2 distance² = ||v1 - v2||²
             = ||v1||² + ||v2||² - 2(v1 · v2)
             = 1 + 1 - 2·cosine_similarity
             = 2(1 - cosine_similarity)

따라서:
L2 distance = √(2(1 - cosine_similarity))
```

#### 거리-유사도 변환표

| Cosine Similarity | L2 Distance | 의미 |
|-------------------|-------------|------|
| 1.0 (완전 동일) | 0.0 | 완벽한 매치 |
| 0.9 | ~0.447 | 매우 유사 |
| 0.8 | ~0.632 | 유사 |
| **0.7** | **~0.775** | **중간 유사도 (임계값)** |
| 0.6 | ~0.894 | 약간 유사 |
| 0.5 | 1.0 | 중립 |
| 0.0 | ~1.414 | 직교 (무관계) |
| -1.0 (반대) | 2.0 | 완전히 다름 |

---

## ⚙️ 임계값 설정 분석

### 현재 설정

**파일**: `nose_lib/pipelines/nose_print_pipeline.py` (Line 18-19)

```python
self.duplicate_threshold = 0.7   # 중복 판단 임계값
self.outlier_threshold = 1.2     # 이상치 판단 임계값
```

### 임계값 의미 및 로직

```python
distances, indices = self.faiss_index.search(vector_to_search, k=1)
distance = float(distances[0][0])  # 가장 가까운 벡터까지의 L2 거리

if distance <= self.duplicate_threshold:  # distance ≤ 0.7
    return {"status": "DUPLICATE", "distance": distance, "id": nearest_id}
    
elif distance > self.outlier_threshold:   # distance > 1.2
    return {"status": "INVALID_IMAGE", "message": "정상적인 비문으로 보이지 않습니다."}
    
else:  # 0.7 < distance ≤ 1.2
    return {"status": "SUCCESS", "vector": vector, "faiss_id": new_faiss_id}
```

### 결정 영역 분석

```
                    L2 거리
0.0 ─────────── 0.7 ──────── 1.2 ────────── 2.0
     DUPLICATE     │  SUCCESS  │  INVALID
     (중복 의심)    │ (새 등록) │ (이상치)
                   │           │
           Cosine ≥ 0.65  Cosine ≈ 0.28
```

#### 1. **DUPLICATE (중복) 판단**: `distance ≤ 0.7`

**Cosine Similarity 환산:**
```
L2 = 0.7
→ cosine_similarity ≥ 0.755 - 0.245 ≈ 0.65~0.76
```

**의미:**
- ✅ 같은 강아지의 비문일 가능성 **높음**
- ✅ 이미 등록된 개체로 판단
- ✅ 신규 등록 거부

**문제점 가능성:**
- ❌ **너무 엄격**할 수 있음
- 같은 강아지인데도 촬영 각도/조명이 다르면 0.7 이상의 거리가 나올 수 있음
- 학습 데이터의 margin=0.6과 비교하면 적절할 수 있음

#### 2. **SUCCESS (새 등록)**: `0.7 < distance ≤ 1.2`

**Cosine Similarity 환산:**
```
L2 = 0.7 ~ 1.2
→ cosine_similarity ≈ 0.28 ~ 0.76
```

**의미:**
- ✅ 새로운 강아지로 판단
- ✅ 기존 등록된 비문과 충분히 다름
- ✅ 신규 등록 진행

#### 3. **INVALID_IMAGE (이상치)**: `distance > 1.2`

**Cosine Similarity 환산:**
```
L2 > 1.2
→ cosine_similarity < 0.28
```

**의미:**
- ⚠️ 정상적인 비문 이미지가 아닐 가능성
- ⚠️ 잘못된 이미지 (예: 블러, 노이즈, 비문이 아닌 다른 부위)
- ✅ 품질 검증 역할

---

## 📈 임계값 타당성 분석

### 1. **학습 Margin과의 관계**

**config.yaml:**
```yaml
train:
  margin: 0.6
  
visualization:
  cosine_threshold: 0.7
```

#### Contrastive Loss 기준 (추정)
```
학습 목표:
- Positive pair (같은 nose): distance < margin (0.6)
- Negative pair (다른 nose): distance > margin (0.6)
```

#### 현재 임계값 비교
```
학습 margin:        0.6
추론 threshold:     0.7  ← 학습보다 0.1 더 관대

→ 합리적! 학습 때보다 약간 여유를 둠
```

### 2. **임계값 설정의 트레이드오프**

#### 시나리오 A: `duplicate_threshold = 0.7` (현재)

**장점:**
- ✅ False Positive (다른 개체를 같다고 판단) 감소
- ✅ 중복 등록 방지 효과적

**단점:**
- ❌ False Negative (같은 개체를 다르다고 판단) 증가 가능
- ❌ 같은 강아지인데 각도/조명 차이로 거부될 수 있음

#### 시나리오 B: `duplicate_threshold = 0.5` (더 관대)

**장점:**
- ✅ False Negative 감소 (같은 강아지를 더 잘 인식)
- ✅ 다양한 촬영 조건 허용

**단점:**
- ❌ False Positive 증가 (다른 강아지를 같다고 오판)
- ❌ 중복 등록 가능성 증가

---

## 🔬 실전 거리 분석 (예시)

### 가정: 512차원 정규화 벡터

```python
# 예시 벡터
v1 = np.random.randn(512)
v1 = v1 / np.linalg.norm(v1)  # L2 정규화

v2 = np.random.randn(512)
v2 = v2 / np.linalg.norm(v2)

# L2 거리 계산
distance = np.linalg.norm(v1 - v2)
print(f"L2 Distance: {distance:.4f}")

# Cosine 유사도 계산
cosine_sim = np.dot(v1, v2)
print(f"Cosine Similarity: {cosine_sim:.4f}")

# 관계 확인
assert abs(distance - np.sqrt(2 * (1 - cosine_sim))) < 0.001
```

### 실제 데이터 예상 분포

```
같은 강아지 (Positive pairs):
- 평균 L2 거리: 0.3 ~ 0.6
- 평균 Cosine: 0.82 ~ 0.95
- 판단: DUPLICATE ✅

다른 강아지 (Negative pairs):
- 평균 L2 거리: 0.8 ~ 1.4
- 평균 Cosine: 0.02 ~ 0.68
- 판단: SUCCESS ✅

저품질 이미지:
- 평균 L2 거리: 1.3 ~ 2.0
- 평균 Cosine: -0.3 ~ 0.26
- 판단: INVALID_IMAGE ✅
```

---

## 🛠️ 임계값 최적화 제안

### 방법 1: 검증 데이터셋 기반 조정

```python
# 1. 검증 세트에서 거리 분포 수집
positive_distances = []  # 같은 개체 쌍
negative_distances = []  # 다른 개체 쌍

# 2. EER (Equal Error Rate) 찾기
from sklearn.metrics import roc_curve

fpr, tpr, thresholds = roc_curve(labels, distances)
eer_threshold = thresholds[np.argmin(np.abs(fpr - (1 - tpr)))]

print(f"Optimal Threshold (EER): {eer_threshold:.4f}")
```

### 방법 2: F1-Score 최대화

```python
from sklearn.metrics import f1_score

best_threshold = 0
best_f1 = 0

for threshold in np.arange(0.3, 1.0, 0.05):
    predictions = distances < threshold
    f1 = f1_score(true_labels, predictions)
    
    if f1 > best_f1:
        best_f1 = f1
        best_threshold = threshold

print(f"Optimal Threshold (F1): {best_threshold:.4f}")
```

### 방법 3: 비즈니스 요구사항 반영

```python
# 중복 등록 방지가 최우선 (보안/의료)
duplicate_threshold = 0.5  # 더 엄격하게

# 사용자 편의성 우선 (일반 서비스)
duplicate_threshold = 0.85  # 더 관대하게
```

---

## 📊 현재 설정 평가

### ✅ 장점

1. **이론적 근거 탄탄**
   - 학습 margin (0.6)보다 약간 관대한 0.7 설정
   - Cosine threshold 0.7과 일관성 유지

2. **3단계 판단 로직**
   - DUPLICATE: 중복 방지
   - SUCCESS: 정상 등록
   - INVALID: 품질 검증
   - → 안전하고 체계적

3. **L2 정규화 벡터 활용**
   - Cosine similarity와 L2 거리의 일관성 보장
   - 스케일 불변성 확보

### ⚠️ 개선 가능 영역

1. **임계값 하드코딩**
   ```python
   # 현재
   self.duplicate_threshold = 0.7
   self.outlier_threshold = 1.2
   
   # 개선안
   def __init__(self, ..., duplicate_threshold=0.7, outlier_threshold=1.2):
       self.duplicate_threshold = duplicate_threshold
       self.outlier_threshold = outlier_threshold
   ```

2. **임계값 검증 부재**
   - 실제 데이터로 검증한 기록 없음
   - ROC 곡선, F1-Score 등 메트릭 필요

3. **동적 임계값 부재**
   - 모든 상황에 동일한 임계값 적용
   - 이미지 품질에 따른 적응형 임계값 고려

---

## 🔮 권장사항

### 1. **즉시 적용 가능**

#### A. 설정 파일로 분리
```yaml
# config.yaml에 추가
inference:
  duplicate_threshold: 0.7
  outlier_threshold: 1.2
  min_confidence: 0.8
```

#### B. 로깅 강화
```python
def process_image(self, ...):
    # ...
    print(f"Distance: {distance:.4f}, Cosine: {1 - distance**2/2:.4f}")
    print(f"Threshold: duplicate={self.duplicate_threshold}, outlier={self.outlier_threshold}")
```

### 2. **중기 개선**

#### A. 검증 데이터셋 구축
```
1. 테스트 세트 준비 (100+ 강아지)
2. 각 강아지당 5+ 이미지
3. 모든 쌍에 대해 거리 계산
4. ROC 곡선 분석
5. 최적 임계값 결정
```

#### B. 메트릭 추적
```python
# 성능 모니터링
metrics = {
    "true_positive": 0,   # 같은 개체를 DUPLICATE로 판단
    "false_positive": 0,  # 다른 개체를 DUPLICATE로 판단
    "true_negative": 0,   # 다른 개체를 SUCCESS로 판단
    "false_negative": 0,  # 같은 개체를 SUCCESS로 판단
}
```

### 3. **장기 개선**

#### A. 적응형 임계값
```python
def adaptive_threshold(self, image_quality_score):
    """이미지 품질에 따라 임계값 조정"""
    if image_quality_score > 0.9:
        return 0.7  # 고품질 → 엄격
    elif image_quality_score > 0.7:
        return 0.8  # 중간 품질
    else:
        return 0.9  # 저품질 → 관대
```

#### B. 앙상블 판단
```python
def ensemble_decision(self, distance, image_quality, nose_confidence):
    """여러 요소를 종합하여 판단"""
    score = (
        0.5 * (1 - distance/2) +      # 거리 기반
        0.3 * image_quality +          # 품질 기반
        0.2 * nose_confidence          # 탐지 신뢰도
    )
    return score > 0.75
```

---

## 📋 요약 및 결론

### 현재 상태

| 항목 | 값 | 평가 |
|------|-----|------|
| **Duplicate Threshold** | 0.7 | ✅ 적절 (margin 0.6 대비) |
| **Outlier Threshold** | 1.2 | ✅ 적절 (품질 필터링) |
| **거리 메트릭** | L2 (정규화 벡터) | ✅ Cosine과 일관성 |
| **검색 방식** | IndexFlatL2 | ✅ 정확도 100% |
| **설정 관리** | 하드코딩 | ⚠️ 개선 필요 |
| **검증** | 미실시 | ❌ 필수 |

### 핵심 인사이트

1. **L2 정규화 + L2 거리 = Cosine 유사도**
   - 수학적으로 일관성 있는 설계 ✅
   
2. **임계값 0.7 = Cosine ~0.76**
   - 학습 margin(0.6)보다 관대
   - 실용적인 설정 ✅
   
3. **3단계 판단 로직**
   - 중복 방지 + 품질 검증
   - 안전한 시스템 설계 ✅

### 최우선 개선 과제

1. 🔴 **검증 데이터셋으로 임계값 검증**
2. 🟡 **설정 파일로 임계값 분리**
3. 🟢 **성능 메트릭 수집 및 모니터링**

---

**작성일**: 2025-10-12  
**작성자**: AI Assistant  
**문서 버전**: 1.0
