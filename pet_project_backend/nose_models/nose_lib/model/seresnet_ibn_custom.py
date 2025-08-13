# =====================================================================================
# --- nose_models/nose_lib/backbone/timm/models/seresnet_ibn_custom.py ---
# =====================================================================================

import torch
import torch.nn as nn
# 'nose_lib' 패키지 내의 다른 모듈을 절대 경로로 임포트합니다.
from nose_lib.backbone.ibnnet.modules import IBN
# 'timm'은 외부 라이브러리이므로 그대로 둡니다.
from timm.layers import SEModule
from timm import create_model

class SEResNeXtBottleneck_IBN(nn.Module):
    expansion = 4
    def __init__(self, inplanes, planes, stride=1, downsample=None, base_width=4, cardinality=32, ibn=False):
        super().__init__()
        D = int(planes * (base_width / 64))
        C = cardinality
        self.conv1 = nn.Conv2d(inplanes, D * C, kernel_size=1, bias=False)
        if ibn:
            self.bn1 = IBN(D * C)
            self.use_relu1 = False
        else:
            self.bn1 = nn.BatchNorm2d(D * C)
            self.use_relu1 = True
        self.conv2 = nn.Conv2d(D * C, D * C, kernel_size=3, stride=stride, padding=1, groups=C, bias=False)
        self.bn2 = nn.BatchNorm2d(D * C)
        self.conv3 = nn.Conv2d(D * C, planes * 4, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm2d(planes * 4)
        self.se = SEModule(planes * 4)
        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        identity = x
        out = self.conv1(x)
        out = self.bn1(out)
        if self.use_relu1:
            out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)
        out = self.conv3(out)
        out = self.bn3(out)
        out = self.se(out)
        if self.downsample is not None:
            identity = self.downsample(x)
        out += identity
        out = self.relu(out)
        return out

class SEResNeXt_IBN(nn.Module):
    def __init__(self, layers=[3, 4, 6, 3], base_width=4, cardinality=32):
        super().__init__()
        block = SEResNeXtBottleneck_IBN
        self.inplanes = 64
        self.conv1 = nn.Conv2d(3, 64, kernel_size=7, stride=2, padding=3, bias=False)
        self.bn1 = nn.BatchNorm2d(64)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        self.layer1 = self._make_layer(block, 64, layers[0], stride=1, ibn=True)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2, ibn=True)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2, ibn=True)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2, ibn=False)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.feature_dim = 512 * block.expansion
        self.fc = nn.Identity()

    def _make_layer(self, block, planes, blocks, stride=1, ibn=False):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes, planes * block.expansion, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(planes * block.expansion),
            )
        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample, ibn=ibn))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes, ibn=ibn))
        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        return x

def seresnext50_ibn_custom(pretrained=False):
    model = SEResNeXt_IBN()
    if pretrained:
        print("Loading pretrained weights from timm seresnext50_32x4d.racm_in1k")
        ref = create_model("seresnext50_32x4d.racm_in1k", pretrained=True)
        ref_dict = ref.state_dict()
        model_dict = model.state_dict()
        matched = {k: v for k, v in ref_dict.items() if k in model_dict and v.shape == model_dict[k].shape}
        model_dict.update(matched)
        model.load_state_dict(model_dict)
    return model