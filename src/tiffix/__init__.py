"""
This module provides functions for image correction.
The implementation was translated and adapted to Python based on MATLAB code originally developed by Yuki Yoneyama.
"""

from pathlib import Path

import numpy as np
import tifffile


def reshape_img(img: np.ndarray) -> np.ndarray:
    original_height, original_width = img.shape
    original_x_center = original_width // 2

    reshaped_height, reshaped_width = original_height*2, original_x_center

    reshaped_img = np.zeros((reshaped_height, reshaped_width), dtype=np.float64)

    odd_col = img[:, :original_x_center]
    even_col = img[:, original_x_center:]

    reshaped_img[0::2] = odd_col
    reshaped_img[1::2] = even_col[:, ::-1]
    return reshaped_img

def load_mean_image(files: list[Path], onset: int, offset: int) -> np.ndarray:
    if onset < 0 or offset >= len(files):
        raise ValueError("onset/offset out of range")

    if onset > offset:
        raise ValueError("onset must be <= offset")

    first_img = tifffile.imread(files[onset])
    acc = np.zeros_like(first_img, dtype=np.float64)

    for i in range(onset, offset + 1):
        img = tifffile.imread(files[i])
        acc += img

    mean_img = acc / (offset - onset + 1)

    return reshape_img(mean_img)

def sine_correction(img: np.ndarray) -> np.ndarray:
    _, w = img.shape
    sin_x = 0.5 * (1 - np.cos(np.pi * np.arange(1, w + 1) / w))
    # interp1d(kind="linear", fill_value="extrapolate") と同じ線形補間を、
    # 補間位置のインデックスと重みを直接計算して行う（先頭列は捨てるので最初から除く）。
    sin_xq = np.linspace(0, 1, w)[1:]

    # 範囲外の点は端の区間を延長して外挿する
    idx = np.clip(np.searchsorted(sin_x, sin_xq, side="right") - 1, 0, w - 2)
    t = (sin_xq - sin_x[idx]) / (sin_x[idx + 1] - sin_x[idx])

    corrected = img[:, idx] * (1 - t) + img[:, idx + 1] * t
    return corrected

def align_img(img: np.ndarray, delta: int = 0):
    h, w = img.shape
    aligned_img = np.zeros((h, w - abs(delta)))
    if delta > 0:
        aligned_img[0::2, :] = img[0::2, delta:]
        aligned_img[1::2, :] = img[1::2, :-delta]
    elif delta < 0:
        delta = abs(delta)
        aligned_img[0::2, :] = img[0::2, :-delta]
        aligned_img[1::2, :] = img[1::2, delta:]
    else:
        return img
    return aligned_img
