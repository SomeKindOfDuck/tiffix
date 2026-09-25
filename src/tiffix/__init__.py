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

def _sine_interp_weights(w: int) -> tuple[np.ndarray, np.ndarray]:
    sin_x = 0.5 * (1 - np.cos(np.pi * np.arange(1, w + 1) / w))
    # interp1d(kind="linear", fill_value="extrapolate") と同じ線形補間を、
    # 補間位置のインデックスと重みを直接計算して行う（先頭列は捨てるので最初から除く）。
    sin_xq = np.linspace(0, 1, w)[1:]

    # 範囲外の点は端の区間を延長して外挿する
    idx = np.clip(np.searchsorted(sin_x, sin_xq, side="right") - 1, 0, w - 2)
    t = (sin_xq - sin_x[idx]) / (sin_x[idx + 1] - sin_x[idx])
    return idx, t

def sine_correction(img: np.ndarray) -> np.ndarray:
    _, w = img.shape
    idx, t = _sine_interp_weights(w)

    corrected = img[:, idx] * (1 - t) + img[:, idx + 1] * t
    return corrected

def correct_raw_img(img: np.ndarray, delta: int = 0) -> np.ndarray:
    """
    sine_correction(align_img(reshape_img(img), delta)) と同じ結果を返す。

    reshape と align は画素の並べ替えだけなので、sine 補正の補間インデックスと合成し、
    元画像から1回の gather で直接求めることで中間配列の生成を省いている。
    """
    original_height, original_width = img.shape
    if original_width % 2 != 0:
        raise ValueError("画像の幅は偶数である必要があります。")

    original_x_center = original_width // 2
    idx, t = _sine_interp_weights(original_x_center - abs(delta))

    # reshape 後の偶数行は img[k, j]、奇数行は img[k, original_width - 1 - j]。
    # align で偶数行は delta (>0) 、奇数行は -delta (>0) だけ列がずれる。
    even_cols = idx + max(delta, 0)
    odd_cols = original_width - 1 - (idx + max(-delta, 0))

    corrected = np.empty((original_height * 2, idx.size), dtype=np.float64)
    corrected[0::2] = img[:, even_cols] * (1 - t) + img[:, even_cols + 1] * t
    corrected[1::2] = img[:, odd_cols] * (1 - t) + img[:, odd_cols - 1] * t
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
