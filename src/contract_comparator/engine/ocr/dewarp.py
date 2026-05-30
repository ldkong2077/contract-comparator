"""
文档去畸变 — 摄像头文档透视变形和倾斜纠正
"""

import logging

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


def _order_points(pts: np.ndarray) -> np.ndarray:
    """将四个点排序为 [左上, 右上, 右下, 左下]"""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # 左上
    rect[2] = pts[np.argmax(s)]   # 右下
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # 右上
    rect[3] = pts[np.argmax(diff)]  # 左下
    return rect


def dewarp_document(img: np.ndarray, aggressive: bool = True) -> np.ndarray:
    """
    文档去畸变：纠正摄像头拍摄的文档透视变形和倾斜

    策略：
    1. 检测最大四边形轮廓（文档边界）
    2. 透视变换拉正
    3. 回退：角度检测 + 旋转（兼容纯扫描件）

    Args:
        img: BGR 图像
        aggressive: 是否使用激进模式（尝试透视变换）

    Returns:
        校正后的图像
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if aggressive:
        # 尝试检测文档边界进行透视校正
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        # 膨胀连接边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # 按面积排序，取最大轮廓
            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            for cnt in contours[:5]:
                area = cv2.contourArea(cnt)
                if area < w * h * 0.1:
                    continue

                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

                if len(approx) == 4:
                    # 找到四边形 → 透视变换
                    pts = approx.reshape(4, 2).astype(np.float32)
                    # 排序点：左上、右上、右下、左下
                    rect = _order_points(pts)
                    dst = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
                    M = cv2.getPerspectiveTransform(rect, dst)
                    warped = cv2.warpPerspective(img, M, (w, h),
                                                  flags=cv2.INTER_CUBIC,
                                                  borderMode=cv2.BORDER_REPLICATE)
                    slog.info("透视校正成功", contour_area=f"{area:.0f}")
                    return warped

    # 回退：标准旋转纠偏（更低的触发阈值）
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) == 0:
        coords = np.column_stack(np.where(gray > 50))

    if len(coords) < 100:
        slog.debug("可用像素不足，跳过纠偏", coords=len(coords))
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    # aggressive 模式使用更低的触发角
    min_angle = 0.2 if aggressive else 0.5

    if abs(angle) > min_angle:
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h),
                                  flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)
        slog.info("旋转纠偏完成", angle=f"{angle:.2f}°")
        return rotated

    slog.debug("无需纠偏", angle=f"{angle:.2f}°")
    return img
