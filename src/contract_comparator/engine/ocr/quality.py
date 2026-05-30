"""
图像质量评估 — 自动判断是否需要预处理
"""

import logging

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class ImageQualityReport:
    """图像质量评估报告"""

    def __init__(self):
        self.contrast_score: float = 0.0        # 0-1，越高越好
        self.blur_score: float = 0.0            # 0-1，越低越好（0=锐利）
        self.noise_level: float = 0.0           # 0-1，越低越好
        self.needs_preprocessing: bool = False
        self.recommended_actions: list[str] = []
        self.overall_quality: float = 0.0       # 0-1 综合质量

    def __repr__(self):
        return (f"Quality(contrast={self.contrast_score:.2f}, blur={self.blur_score:.2f}, "
                f"noise={self.noise_level:.2f}, overall={self.overall_quality:.2f}, "
                f"need_preprocess={self.needs_preprocessing})")


def _assess_contrast(gray: np.ndarray) -> float:
    """评估对比度 (0-1)"""
    rms = np.std(gray.astype(np.float64)) / 128.0
    return min(rms, 1.0)


def _assess_blur(gray: np.ndarray) -> float:
    """
    评估模糊度 (0-1, 0=锐利)
    使用拉普拉斯方差（Variance of Laplacian）
    """
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    var = lap.var()
    score = max(0.0, min(1.0 - var / 500.0, 1.0))
    return score


def _assess_noise(gray: np.ndarray) -> float:
    """
    评估噪声水平 (0-1)
    使用中值滤波差分法
    """
    denoised = cv2.medianBlur(gray, 3)
    diff = np.abs(gray.astype(np.float32) - denoised.astype(np.float32))
    noise = np.mean(diff) / 50.0
    return min(noise, 1.0)


def assess_image_quality(img: np.ndarray) -> ImageQualityReport:
    """
    评估图像质量并给出预处理建议

    Args:
        img: BGR 图像

    Returns:
        ImageQualityReport 对象
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    report = ImageQualityReport()

    report.contrast_score = _assess_contrast(gray)
    report.blur_score = _assess_blur(gray)
    report.noise_level = _assess_noise(gray)

    # 综合评分
    report.overall_quality = (
        0.4 * report.contrast_score +
        0.35 * (1.0 - report.blur_score) +
        0.25 * (1.0 - report.noise_level)
    )

    # 自动决策
    if report.contrast_score < 0.3:
        report.needs_preprocessing = True
        report.recommended_actions.append("contrast_enhance")
    if report.blur_score > 0.6:
        report.needs_preprocessing = True
        report.recommended_actions.append("sharpen")
    if report.noise_level > 0.5:
        report.needs_preprocessing = True
        report.recommended_actions.append("denoise")
    if report.overall_quality < 0.4:
        report.needs_preprocessing = True
        if not report.recommended_actions:
            report.recommended_actions.append("full_preprocess")

    slog.info("图像质量评估完成",
              contrast=f"{report.contrast_score:.2f}",
              blur=f"{report.blur_score:.2f}",
              noise=f"{report.noise_level:.2f}",
              overall=f"{report.overall_quality:.2f}",
              needs_prep=report.needs_preprocessing,
              actions=",".join(report.recommended_actions) if report.recommended_actions else "none")
    return report
