# =====================================================================================
# --- nose_models/nose_lib/model/siamese_cosine.py ---
# =====================================================================================
import torch
import torch.nn as nn
import torch.nn.functional as F
# 'nose_lib'를 기준으로 절대 경로 임포트를 사용합니다.
from nose_lib.backbone.backbone_build import get_backbone

class SiameseNetwork(nn.Module):
    def __init__(self, backbone_name: str, in_features: int, feature_dim: int = 256, pretrained: bool = True):
        super().__init__()
        self.backbone = get_backbone(backbone_name, pretrained=pretrained)
        proj_hidden1 = 1024
        if in_features > 1024:
            proj_hidden1 = min(in_features, 2048)
        elif in_features < 512:
            proj_hidden1 = 512
        proj_hidden2 = 512
        if proj_hidden1 <= proj_hidden2:
            proj_hidden2 = max(feature_dim, proj_hidden1 // 2)
        print(f"프로젝터 구성: 입력={in_features} -> 은닉1={proj_hidden1} -> 은닉2={proj_hidden2} -> 출력={feature_dim}")
        if proj_hidden1 == proj_hidden2 and proj_hidden1 == feature_dim:
            self.projector = nn.Linear(in_features, feature_dim)
        elif proj_hidden1 == proj_hidden2:
            self.projector = nn.Sequential(
                nn.Linear(in_features, proj_hidden1),
                nn.BatchNorm1d(proj_hidden1),
                nn.GELU(),
                nn.Dropout(0.2),
                nn.Linear(proj_hidden1, feature_dim)
            )
        else:
            self.projector = nn.Sequential(
                nn.Linear(in_features, proj_hidden1),
                nn.BatchNorm1d(proj_hidden1),
                nn.GELU(),
                nn.Dropout(0.2),
                nn.Linear(proj_hidden1, proj_hidden2),
                nn.BatchNorm1d(proj_hidden2),
                nn.GELU(),
                nn.Dropout(0.2),
                nn.Linear(proj_hidden2, feature_dim)
            )

    def extract(self, x: torch.Tensor, normalize: bool = True) -> torch.Tensor:
        x = self.backbone(x)
        x = self.projector(x)
        return F.normalize(x, dim=1) if normalize else x

    def forward(self, x1: torch.Tensor, x2: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z1 = self.extract(x1, normalize=True)
        z2 = self.extract(x2, normalize=True)
        return z1, z2