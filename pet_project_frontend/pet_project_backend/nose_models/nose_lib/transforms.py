from torchvision import transforms
import cv2
import numpy as np
from PIL import Image

class CLAHEandSharpen:
    def __init__(self, clip_limit=2.0, tile_grid_size=(8, 8), sigma=1.0):
        self.clip_limit = clip_limit
        self.tile_grid_size = tile_grid_size
        self.sigma = sigma

    def __call__(self, img):
        img_np = np.array(img)
        if len(img_np.shape) == 2:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        elif img_np.shape[2] == 1:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
        lab = cv2.cvtColor(img_np, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=self.clip_limit, tileGridSize=self.tile_grid_size)
        l_eq = clahe.apply(l)
        lab_eq = cv2.merge((l_eq, a, b))
        img_eq = cv2.cvtColor(lab_eq, cv2.COLOR_LAB2RGB)
        blur = cv2.GaussianBlur(img_eq, (0, 0), sigmaX=self.sigma)
        sharpened = cv2.addWeighted(img_eq, 1.5, blur, -0.5, 0)
        return Image.fromarray(sharpened)

def get_train_transform(img_height: int, img_width: int, use_clahe_sharpen: bool = True):
    transform_list = [transforms.Resize((img_height, img_width))]
    if use_clahe_sharpen:
        transform_list.append(CLAHEandSharpen(clip_limit=2.0, tile_grid_size=(8, 8), sigma=1.0))
    transform_list.extend([
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomAffine(degrees=10, translate=(0.05, 0.05), scale=(0.9, 1.1)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    return transforms.Compose(transform_list)

def get_val_transform(img_height: int, img_width: int, use_clahe_sharpen: bool = True):
    transform_list = [transforms.Resize((img_height, img_width))]
    if use_clahe_sharpen:
        transform_list.append(CLAHEandSharpen(clip_limit=2.0, tile_grid_size=(8, 8), sigma=1.0))
    transform_list.extend([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    return transforms.Compose(transform_list)