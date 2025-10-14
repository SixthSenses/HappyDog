"""
비문 인식 임계값 시각화 및 분석 도구

Usage:
    python analyze_thresholds.py
"""
import numpy as np
import matplotlib.pyplot as plt

def l2_to_cosine(l2_distance):
    """L2 거리를 Cosine 유사도로 변환 (정규화 벡터 가정)"""
    return 1 - (l2_distance ** 2) / 2

def cosine_to_l2(cosine_sim):
    """Cosine 유사도를 L2 거리로 변환"""
    return np.sqrt(2 * (1 - cosine_sim))

def visualize_thresholds():
    """현재 임계값 설정을 시각화"""
    
    # 현재 설정
    DUPLICATE_THRESHOLD = 0.7
    OUTLIER_THRESHOLD = 1.2
    TRAIN_MARGIN = 0.6
    
    # L2 거리 범위
    l2_distances = np.linspace(0, 2.0, 1000)
    cosine_sims = [l2_to_cosine(d) for d in l2_distances]
    
    # 플롯 생성
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # === 상단 플롯: L2 거리 분포 ===
    ax1.axvspan(0, DUPLICATE_THRESHOLD, alpha=0.3, color='green', label='DUPLICATE (중복)')
    ax1.axvspan(DUPLICATE_THRESHOLD, OUTLIER_THRESHOLD, alpha=0.3, color='blue', label='SUCCESS (새 등록)')
    ax1.axvspan(OUTLIER_THRESHOLD, 2.0, alpha=0.3, color='red', label='INVALID (이상치)')
    
    # 임계값 라인
    ax1.axvline(DUPLICATE_THRESHOLD, color='green', linestyle='--', linewidth=2, label=f'Duplicate Threshold: {DUPLICATE_THRESHOLD}')
    ax1.axvline(OUTLIER_THRESHOLD, color='red', linestyle='--', linewidth=2, label=f'Outlier Threshold: {OUTLIER_THRESHOLD}')
    ax1.axvline(TRAIN_MARGIN, color='orange', linestyle=':', linewidth=2, label=f'Train Margin: {TRAIN_MARGIN}')
    
    ax1.set_xlabel('L2 Distance', fontsize=12)
    ax1.set_ylabel('Density', fontsize=12)
    ax1.set_title('비문 인식 임계값 설정 (L2 Distance)', fontsize=14, fontweight='bold')
    ax1.set_xlim(0, 2.0)
    ax1.legend(loc='upper right')
    ax1.grid(True, alpha=0.3)
    
    # === 하단 플롯: L2 ↔ Cosine 관계 ===
    ax2.plot(l2_distances, cosine_sims, linewidth=2, color='navy')
    
    # 주요 지점 표시
    points = [
        (0.0, 1.0, 'Perfect Match'),
        (TRAIN_MARGIN, l2_to_cosine(TRAIN_MARGIN), f'Train Margin\n(L2={TRAIN_MARGIN:.2f}, Cos={l2_to_cosine(TRAIN_MARGIN):.2f})'),
        (DUPLICATE_THRESHOLD, l2_to_cosine(DUPLICATE_THRESHOLD), f'Duplicate\n(L2={DUPLICATE_THRESHOLD:.2f}, Cos={l2_to_cosine(DUPLICATE_THRESHOLD):.2f})'),
        (OUTLIER_THRESHOLD, l2_to_cosine(OUTLIER_THRESHOLD), f'Outlier\n(L2={OUTLIER_THRESHOLD:.2f}, Cos={l2_to_cosine(OUTLIER_THRESHOLD):.2f})'),
        (1.414, 0.0, 'Orthogonal'),
    ]
    
    for l2, cos, label in points:
        ax2.plot(l2, cos, 'ro', markersize=8)
        ax2.annotate(label, xy=(l2, cos), xytext=(10, 10), 
                    textcoords='offset points', fontsize=9,
                    bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))
    
    ax2.set_xlabel('L2 Distance', fontsize=12)
    ax2.set_ylabel('Cosine Similarity', fontsize=12)
    ax2.set_title('L2 Distance ↔ Cosine Similarity 관계', fontsize=14, fontweight='bold')
    ax2.set_xlim(0, 2.0)
    ax2.set_ylim(-0.1, 1.1)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('nose_print_threshold_analysis.png', dpi=300, bbox_inches='tight')
    print("✅ 시각화 저장 완료: nose_print_threshold_analysis.png")
    plt.show()

def analyze_threshold_impact():
    """임계값 변화에 따른 영향 분석"""
    
    print("\n" + "="*70)
    print("비문 인식 임계값 영향 분석")
    print("="*70)
    
    # 현재 설정
    current_dup = 0.7
    current_out = 1.2
    
    print(f"\n[현재 설정]")
    print(f"  Duplicate Threshold: {current_dup}")
    print(f"  Outlier Threshold:   {current_out}")
    print(f"  Cosine (Duplicate):  {l2_to_cosine(current_dup):.4f}")
    print(f"  Cosine (Outlier):    {l2_to_cosine(current_out):.4f}")
    
    # 시뮬레이션: 다양한 임계값 설정
    scenarios = [
        ("매우 엄격 (보안 우선)", 0.5, 1.0),
        ("엄격 (중복 방지)", 0.6, 1.1),
        ("현재 설정", 0.7, 1.2),
        ("관대 (편의성 우선)", 0.8, 1.3),
        ("매우 관대 (사용자 친화)", 0.9, 1.4),
    ]
    
    print(f"\n{'시나리오':<25} | {'Dup TH':<8} | {'Out TH':<8} | {'Dup Cosine':<12} | {'예상 효과':<30}")
    print("-" * 110)
    
    for name, dup_th, out_th in scenarios:
        cos_dup = l2_to_cosine(dup_th)
        
        if dup_th < 0.6:
            effect = "❌ False Negative ↑ (같은 개체 거부)"
        elif dup_th < 0.7:
            effect = "⚠️ 균형잡힘 (약간 엄격)"
        elif dup_th < 0.8:
            effect = "✅ 균형잡힘 (추천)"
        elif dup_th < 0.9:
            effect = "⚠️ False Positive ↑ (다른 개체 허용)"
        else:
            effect = "❌ 중복 등록 위험 높음"
        
        print(f"{name:<25} | {dup_th:<8.2f} | {out_th:<8.2f} | {cos_dup:<12.4f} | {effect:<30}")
    
    print("\n" + "="*70)

def calculate_distance_statistics():
    """예상 거리 분포 통계"""
    
    print("\n" + "="*70)
    print("예상 거리 분포 통계 (이론값)")
    print("="*70)
    
    # 시뮬레이션 데이터 생성
    np.random.seed(42)
    
    # 같은 개체 (Positive pairs)
    positive_vectors = []
    base_vector = np.random.randn(512)
    base_vector = base_vector / np.linalg.norm(base_vector)
    
    for _ in range(100):
        noise = np.random.randn(512) * 0.3  # 약간의 변형
        perturbed = base_vector + noise
        perturbed = perturbed / np.linalg.norm(perturbed)
        positive_vectors.append(perturbed)
    
    positive_distances = [np.linalg.norm(base_vector - v) for v in positive_vectors]
    
    # 다른 개체 (Negative pairs)
    negative_vectors = []
    for _ in range(100):
        random_vector = np.random.randn(512)
        random_vector = random_vector / np.linalg.norm(random_vector)
        negative_vectors.append(random_vector)
    
    negative_distances = [np.linalg.norm(base_vector - v) for v in negative_vectors]
    
    print(f"\n[같은 개체 (Positive Pairs)]")
    print(f"  평균 L2 거리:        {np.mean(positive_distances):.4f}")
    print(f"  표준편차:           {np.std(positive_distances):.4f}")
    print(f"  최소-최대:          {np.min(positive_distances):.4f} - {np.max(positive_distances):.4f}")
    print(f"  평균 Cosine 유사도: {np.mean([l2_to_cosine(d) for d in positive_distances]):.4f}")
    
    print(f"\n[다른 개체 (Negative Pairs)]")
    print(f"  평균 L2 거리:        {np.mean(negative_distances):.4f}")
    print(f"  표준편차:           {np.std(negative_distances):.4f}")
    print(f"  최소-최대:          {np.min(negative_distances):.4f} - {np.max(negative_distances):.4f}")
    print(f"  평균 Cosine 유사도: {np.mean([l2_to_cosine(d) for d in negative_distances]):.4f}")
    
    # 임계값 평가
    dup_threshold = 0.7
    false_negative_rate = sum(1 for d in positive_distances if d > dup_threshold) / len(positive_distances)
    false_positive_rate = sum(1 for d in negative_distances if d <= dup_threshold) / len(negative_distances)
    
    print(f"\n[임계값 {dup_threshold} 평가]")
    print(f"  False Negative Rate: {false_negative_rate:.2%} (같은 개체를 다르다고 판단)")
    print(f"  False Positive Rate: {false_positive_rate:.2%} (다른 개체를 같다고 판단)")
    
    print("\n" + "="*70)

def main():
    """메인 분석 실행"""
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║       비문 인식 시스템 - 임계값 분석 도구                    ║
    ║       Nose Print Recognition - Threshold Analysis            ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # 1. 임계값 영향 분석
    analyze_threshold_impact()
    
    # 2. 거리 통계 (시뮬레이션)
    calculate_distance_statistics()
    
    # 3. 시각화
    try:
        visualize_thresholds()
    except Exception as e:
        print(f"\n⚠️ 시각화 건너뜀 (matplotlib 필요): {e}")
    
    print("\n" + "="*70)
    print("분석 완료!")
    print("="*70)
    print("\n📊 권장사항:")
    print("  1. 실제 데이터로 검증 필요 (현재는 이론값)")
    print("  2. ROC 곡선 분석으로 최적 임계값 결정")
    print("  3. 비즈니스 요구사항에 따라 조정")
    print("  4. A/B 테스트로 사용자 경험 비교")
    print("\n")

if __name__ == "__main__":
    main()
