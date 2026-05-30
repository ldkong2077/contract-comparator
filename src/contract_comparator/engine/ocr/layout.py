"""
版面分析 — 投影轮廓法检测表格区域和多栏布局
"""

import logging

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger
from contract_comparator.engine.ocr.binarize import adaptive_binarize

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class LayoutRegion:
    """版面区域"""

    def __init__(self, x1: int, y1: int, x2: int, y2: int, region_type: str):
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.type = region_type  # "text" / "table" / "image" / "header" / "footer"

    @property
    def bbox(self):
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def area(self):
        return (self.x2 - self.x1) * (self.y2 - self.y1)

    def __repr__(self):
        return f"LayoutRegion({self.type}, ({self.x1},{self.y1})-({self.x2},{self.y2}))"


def _horizontal_projection(binary: np.ndarray) -> np.ndarray:
    """水平投影：每行的黑色像素数"""
    return np.sum(binary == 0, axis=1).astype(np.int32)


def _vertical_projection(binary: np.ndarray) -> np.ndarray:
    """垂直投影：每列的黑色像素数"""
    return np.sum(binary == 0, axis=0).astype(np.int32)


def detect_table_regions(binary: np.ndarray, min_line_length_ratio: float = 0.3) -> list[LayoutRegion]:
    """
    通过投影轮廓检测表格区域
    策略：表格区域通常有大量水平/垂直线条，投影曲线呈现规律性尖峰

    Args:
        binary: 二值图像（黑底白字需反转）
        min_line_length_ratio: 最小线条长度占比

    Returns:
        检测到的表格区域列表
    """
    h, w = binary.shape[:2]
    # 确保黑字白底
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)

    # 检测水平线和竖直线
    h_kernel_len = max(int(w * min_line_length_ratio), 20)
    v_kernel_len = max(int(h * min_line_length_ratio), 20)

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))

    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)

    # 合并水平垂直线
    table_mask = cv2.addWeighted(h_lines, 0.5, v_lines, 0.5, 0)
    table_mask = cv2.threshold(table_mask, 127, 255, cv2.THRESH_BINARY)[1]

    # 膨胀合并邻近区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    table_mask = cv2.dilate(table_mask, kernel, iterations=2)

    # 连通域分析
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(table_mask, connectivity=8)

    regions = []
    min_area = (w * h) * 0.005  # 面积过小忽略

    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if area < min_area:
            continue
        regions.append(LayoutRegion(x, y, x + bw, y + bh, "table"))

    slog.debug("表格区域检测完成", table_regions=len(regions))
    return regions


def detect_columns(binary: np.ndarray, min_gap_width: int = 30, min_col_width: int = 100) -> list[LayoutRegion]:
    """
    通过垂直投影检测多栏布局

    Args:
        binary: 二值图像
        min_gap_width: 栏间最小空隙宽度
        min_col_width: 最小栏宽

    Returns:
        栏区域列表
    """
    h, w = binary.shape[:2]
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)

    v_proj = _vertical_projection(binary)
    # 平滑投影
    v_proj_smooth = np.convolve(v_proj, np.ones(10) / 10, mode="same")

    threshold = np.mean(v_proj_smooth) * 0.3
    gaps = v_proj_smooth < threshold

    # 寻找连续间隙
    gap_starts = []
    gap_ends = []
    in_gap = False
    for i, is_gap in enumerate(gaps):
        if is_gap and not in_gap:
            gap_starts.append(i)
            in_gap = True
        elif not is_gap and in_gap:
            gap_ends.append(i)
            in_gap = False
    if in_gap:
        gap_ends.append(w)

    # 过滤太小/太大的间隙
    valid_gaps = [(s, e) for s, e in zip(gap_starts, gap_ends) if min_gap_width <= (e - s) < w * 0.6]

    columns = []
    prev_end = 0
    for gs, ge in valid_gaps:
        col_w = gs - prev_end
        if col_w >= min_col_width:
            columns.append(LayoutRegion(prev_end, 0, gs, h, "text"))
        prev_end = ge
    # 最后一栏
    if w - prev_end >= min_col_width:
        columns.append(LayoutRegion(prev_end, 0, w, h, "text"))

    # 如果只检测到1栏，不分割
    if len(columns) <= 1:
        return [LayoutRegion(0, 0, w, h, "text")]

    slog.debug("多栏检测完成", columns=len(columns))
    return columns


def layout_analysis(img: np.ndarray) -> dict:
    """
    完整版面分析

    Returns:
        {
            "tables": [LayoutRegion, ...],
            "columns": [LayoutRegion, ...],
            "width": int,
            "height": int,
        }
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    binary = adaptive_binarize(img, method="auto")

    tables = detect_table_regions(binary)
    columns = detect_columns(binary)

    result = {
        "tables": tables,
        "columns": columns,
        "width": img.shape[1],
        "height": img.shape[0],
    }
    slog.info("版面分析完成", tables=len(tables), columns=len(columns),
              size=f"{img.shape[1]}x{img.shape[0]}")
    return result
