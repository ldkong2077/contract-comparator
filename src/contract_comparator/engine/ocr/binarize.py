"""
自适应二值化 — Otsu + Sauvola 局部阈值
"""

import logging

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


def _apply_otsu_binarize(gray: np.ndarray) -> np.ndarray:
    """全局 Otsu 二值化"""
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def _apply_sauvola(gray: np.ndarray, window_size: int = 31, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """
    Sauvola 局部自适应阈值
    公式: T = mean * (1 + k * (std / r - 1))
    """
    gray_f = gray.astype(np.float64)
    sq = gray_f * gray_f

    # 积分图加速
    mean = cv2.boxFilter(gray_f, cv2.CV_64F, (window_size, window_size), normalize=True)
    sq_mean = cv2.boxFilter(sq, cv2.CV_64F, (window_size, window_size), normalize=True)
    std = np.sqrt(np.maximum(sq_mean - mean * mean, 0))

    threshold = mean * (1.0 + k * (std / r - 1.0))
    binary = np.where(gray_f > threshold, 255, 0).astype(np.uint8)
    return binary


def adaptive_binarize(img: np.ndarray, method: str = "auto") -> np.ndarray:
    """
    自适应二值化：根据图像特性自动选择 Otsu 或 Sauvola

    Args:
        img: BGR 彩色图像
        method: "otsu" / "sauvola" / "auto"（自动选择）

    Returns:
        二值化后的灰度图像
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if method == "otsu":
        slog.debug("使用 Otsu 二值化")
        return _apply_otsu_binarize(gray)

    if method == "sauvola":
        slog.debug("使用 Sauvola 局部二值化", window_size=31)
        return _apply_sauvola(gray)

    # auto: 根据图像性质自动选择
    h, w = gray.shape[:2]
    # 检查光照均匀性：把图像分成 4x4 块，比较各块均值的方差
    block_h, block_w = h // 4, w // 4
    block_means = []
    for i in range(4):
        for j in range(4):
            block = gray[i * block_h:(i + 1) * block_h, j * block_w:(j + 1) * block_w]
            block_means.append(np.mean(block))
    illumination_var = np.var(block_means)

    if illumination_var > 800 or min(h, w) < 800:
        slog.debug("自动选择 Sauvola（光照不均或小尺寸）", ill_var=f"{illumination_var:.1f}", size=f"{w}x{h}")
        return _apply_sauvola(gray)
    else:
        slog.debug("自动选择 Otsu（光照均匀）", ill_var=f"{illumination_var:.1f}", size=f"{w}x{h}")
        return _apply_otsu_binarize(gray)
