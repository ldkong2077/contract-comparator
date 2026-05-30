"""
增强版图像预处理器
"""

import logging
import os

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger
from contract_comparator.engine.ocr.quality import assess_image_quality

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class ImagePreprocessor:
    """图像预处理器（补偿 RapidOCR 无内置文档预处理的不足）"""

    @staticmethod
    def preprocess(image_path: str, config: dict | None = None) -> np.ndarray:
        """
        对图像进行预处理

        Args:
            image_path: 图片路径
            config: 预处理配置

        Returns:
            预处理后的图像（numpy array）
        """
        # 延迟导入避免循环依赖
        from config import OCR_CONFIG, IMAGE_CONFIG

        if config is None:
            config = OCR_CONFIG.get("preprocess", {})

        assert config is not None

        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        # 检查图片大小是否超过配置限制
        img_size_mb = os.path.getsize(image_path) / (1024 * 1024)
        max_size = IMAGE_CONFIG.get("max_image_size_mb", 20)
        if img_size_mb > max_size:
            raise ValueError(
                f"图片文件过大: {img_size_mb:.1f}MB > {max_size}MB (max_image_size_mb), "
                f"请压缩后重试: {os.path.basename(image_path)}"
            )

        slog.debug("图像读取完成", path=os.path.basename(image_path),
                   size=f"{img.shape[1]}x{img.shape[0]}")

        if not config.get("enable", True):
            return img

        # 0. 质量评估驱动的自适应预处理
        quality = assess_image_quality(img)
        if quality.needs_preprocessing:
            slog.info("检测到图像质量问题，启用自适应预处理",
                      actions=",".join(quality.recommended_actions))

        # 1. 去噪
        if config.get("denoise", True):
            img = cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)
            slog.debug("去噪完成")

        # 2. 对比度增强（CLAHE）
        need_contrast = config.get("contrast_enhance", False) or "contrast_enhance" in quality.recommended_actions
        if need_contrast:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(l_channel)
            img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            slog.debug("CLAHE 对比度增强完成")

        # 3. 锐化
        need_sharpen = config.get("sharpen", False) or "sharpen" in quality.recommended_actions
        if need_sharpen:
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            img = cv2.filter2D(img, -1, kernel)
            slog.debug("锐化完成")

        return img

    @staticmethod
    def deskew_image(img: np.ndarray, aggressive: bool = False) -> np.ndarray:
        """
        自动纠偏（检测文本角度并旋转矫正）

        Args:
            img: 输入图像
            aggressive: 是否使用激进模式（包含透视校正）

        Returns:
            纠偏后的图像
        """
        min_angle = 0.2 if aggressive else 0.5
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)

        coords = np.column_stack(np.where(gray > 0))
        if len(coords) == 0:
            return img

        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) > min_angle:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                img, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            slog.debug("旋转纠偏完成", angle=f"{angle:.2f}°")
        else:
            rotated = img
        return rotated
