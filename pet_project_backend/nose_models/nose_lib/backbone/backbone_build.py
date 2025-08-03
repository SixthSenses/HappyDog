# pet_project_backend/nose_models/nose_lib/backbone/backbone_build.py

from nose_lib.model.seresnet_ibn_custom import seresnext50_ibn_custom

def get_backbone(name: str, pretrained: bool = False):
    """
    지정된 이름의 백본 모델을 생성합니다.
    현재는 'seresnext50_ibn_custom' 모델만 지원합니다.

    :param name: 생성할 백본 모델의 이름
    :param pretrained: 사전 학습된 가중치를 사용할지 여부
    :return: 생성된 Pytorch 모델 객체
    """
    print(f"백본 생성 요청: '{name}', 사전 학습 가중치 사용: {pretrained}")

    if name == "seresnext50_ibn_custom":
        # 이전에 정의한 커스텀 모델 생성 함수를 직접 호출합니다.
        return seresnext50_ibn_custom(pretrained=pretrained)
    else:
        # 지원하지 않는 모델 이름이 들어올 경우 명확한 에러를 발생시킵니다.
        raise ValueError(f"지원하지 않는 백본 이름입니다: '{name}'")