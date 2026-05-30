"""
主 OCR 引擎 — RapidOCR 为主，支持多引擎回退和后校正
"""

import logging
import os

import cv2
import numpy as np
from rapidocr import RapidOCR, LangRec

from contract_comparator.config import OCR_CONFIG
from contract_comparator.engine.ocr.logger import StructuredLogger
from contract_comparator.engine.ocr.binarize import adaptive_binarize
from contract_comparator.engine.ocr.layout import layout_analysis
from contract_comparator.engine.ocr.dewarp import dewarp_document
from contract_comparator.engine.ocr.quality import assess_image_quality, ImageQualityReport
from contract_comparator.engine.ocr.fallback import FallbackEngine
from contract_comparator.engine.ocr.postcorrector import OCRPostCorrector
from contract_comparator.engine.ocr.preprocessor import ImagePreprocessor

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class OCREngine:
    """OCR 识别引擎（RapidOCR 为主，支持多引擎回退和后校正）"""

    def __init__(self, enable_fallback: bool = False, enable_post_correct: bool = True,
                 fallback_order: list[str] | None = None):
        """
        Args:
            enable_fallback: 是否启用多引擎回退
            enable_post_correct: 是否启用置信度后校正
            fallback_order: 回退引擎顺序，默认 ["easyocr", "tesseract"]
        """
        self.ocr = None
        self.preprocessor = ImagePreprocessor()
        self._initialized = False
        self.enable_fallback = enable_fallback
        self.enable_post_correct = enable_post_correct
        self.fallback_order = fallback_order or ["easyocr", "tesseract"]

    def initialize(self):
        """初始化 RapidOCR（首次调用会下载模型）"""
        if self._initialized:
            return

        slog.info("正在初始化 RapidOCR...")
        try:
            self.ocr = RapidOCR(
                params={
                    "Global.text_score": OCR_CONFIG["text_score"],
                    "Rec.lang_type": LangRec.CH,
                }
            )
            self._initialized = True
            slog.info("RapidOCR 初始化完成")
        except Exception as e:
            slog.error("RapidOCR 初始化失败", error=str(e))
            raise RuntimeError(f"RapidOCR 初始化失败: {e}") from e

    # ── 公共 API ──────────────────────────────────────────

    def recognize_image(self, image_path: str) -> list[dict]:
        """
        识别单张图片

        Args:
            image_path: 图片路径

        Returns:
            识别结果列表，每项包含:
            - text: 识别文本
            - confidence: 置信度 (0-1)
            - bbox: 边界框坐标 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        """
        if not self._initialized:
            self.initialize()

        if self.ocr is None:
            raise RuntimeError("OCR 引擎初始化失败")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片不存在: {image_path}")

        preprocess_config = OCR_CONFIG.get("preprocess", {})
        if preprocess_config.get("enable", True):
            processed_img = self.preprocessor.preprocess(image_path)
            if preprocess_config.get("deskew", True):
                processed_img = self.preprocessor.deskew_image(processed_img)
            img_input = processed_img
        else:
            img_input = image_path

        slog.debug("开始 RapidOCR 识别", path=os.path.basename(image_path))
        result = self.ocr(img_input)

        parsed_results = []
        if result and result.txts:
            for i in range(len(result.txts)):
                parsed_results.append({
                    "text": result.txts[i],
                    "confidence": result.scores[i],
                    "bbox": result.boxes[i],
                })

        slog.info("RapidOCR 识别完成", path=os.path.basename(image_path),
                  texts=len(parsed_results))

        if len(parsed_results) == 0 and self.enable_fallback:
            slog.warning("RapidOCR 未识别到文本，启用回退引擎",
                         path=os.path.basename(image_path))
            parsed_results = FallbackEngine.fallback_recognize(
                img_input, self.fallback_order
            )

        if self.enable_post_correct and parsed_results:
            parsed_results = OCRPostCorrector.correct_results(parsed_results)

        return parsed_results

    def recognize_pdf(self, image_paths: list[str]) -> list[dict]:
        """
        识别 PDF 所有页

        Args:
            image_paths: 图片路径列表

        Returns:
            所有页的识别结果
        """
        all_results = []
        total_pages = len(image_paths)
        slog.info("开始批量 PDF 识别", pages=total_pages)

        for i, img_path in enumerate(image_paths):
            slog.info(f"正在识别第 {i + 1}/{total_pages} 页...",
                      page=i + 1, file=os.path.basename(img_path))
            page_results = self.recognize_image(img_path)

            for item in page_results:
                item["page"] = i + 1

            all_results.extend(page_results)
            slog.info(f"第 {i + 1} 页识别完成", page=i + 1, texts=len(page_results))

        slog.info("PDF 批量识别完成", total_pages=total_pages, total_texts=len(all_results))
        return all_results

    def get_full_text(self, results: list[dict]) -> str:
        """
        将 OCR 结果合并为完整文本（按阅读顺序排序）
        """
        if not results:
            return ""

        heights = []
        for item in results:
            bbox = item["bbox"]
            ys = [pt[1] for pt in bbox]
            h = max(ys) - min(ys)
            if h > 0:
                heights.append(h)
        avg_height = np.mean(heights) if heights else 20
        Y_TOLERANCE = max(avg_height * 0.5, 8)

        pages = {}
        for item in results:
            page = item.get("page", 1)
            if page not in pages:
                pages[page] = []
            pages[page].append(item)

        full_text = []
        for page_num in sorted(pages.keys()):
            items = pages[page_num]
            items_sorted = sorted(items, key=lambda x: x["bbox"][0][1])

            rows = []
            current_row = [items_sorted[0]]
            for item in items_sorted[1:]:
                if abs(item["bbox"][0][1] - current_row[-1]["bbox"][0][1]) <= Y_TOLERANCE:
                    current_row.append(item)
                else:
                    rows.append(current_row)
                    current_row = [item]
            rows.append(current_row)

            page_lines = []
            for row in rows:
                row_sorted = sorted(row, key=lambda x: x["bbox"][0][0])

                if len(row_sorted) >= 3:
                    gaps = []
                    for i in range(len(row_sorted) - 1):
                        curr_right = max(pt[0] for pt in row_sorted[i]["bbox"])
                        next_left = min(pt[0] for pt in row_sorted[i + 1]["bbox"])
                        gaps.append(next_left - curr_right)
                    rtl_count = sum(1 for g in gaps if g < -5)
                    if rtl_count > len(gaps) * 0.6:
                        row_sorted = list(reversed(row_sorted))

                merged_segments = []
                current_segment = [row_sorted[0]]
                for i in range(1, len(row_sorted)):
                    curr_right = max(pt[0] for pt in row_sorted[i - 1]["bbox"])
                    next_left = min(pt[0] for pt in row_sorted[i]["bbox"])
                    gap = next_left - curr_right
                    curr_width = max(pt[0] for pt in row_sorted[i - 1]["bbox"]) - min(pt[0] for pt in row_sorted[i - 1]["bbox"])
                    avg_char_width = max(curr_width / max(len(row_sorted[i - 1]["text"]), 1), 5)
                    if gap < avg_char_width * 1.5:
                        current_segment.append(row_sorted[i])
                    else:
                        merged_segments.append(current_segment)
                        current_segment = [row_sorted[i]]
                merged_segments.append(current_segment)

                segment_texts = []
                for seg in merged_segments:
                    seg_text = "".join(item["text"] for item in seg)
                    segment_texts.append(seg_text)
                line_text = " ".join(segment_texts)
                page_lines.append(line_text)

            page_text = "\n".join(page_lines)
            full_text.append(f"--- 第 {page_num} 页 ---\n{page_text}")

        return "\n\n".join(full_text)

    def get_low_confidence_items(self, results: list[dict], threshold: float | None = None) -> list[dict]:
        """
        获取低置信度的识别结果

        Args:
            results: OCR 识别结果
            threshold: 置信度阈值（默认使用配置中的值）

        Returns:
            低置信度项目列表
        """
        if threshold is None:
            threshold = OCR_CONFIG["rec_score_thresh"]

        low_items = [
            item for item in results
            if item["confidence"] < threshold
        ]
        slog.debug("低置信度筛选", threshold=threshold,
                   low_count=len(low_items), total=len(results))
        return low_items

    # ── 增强 API ────────────────────────────────────────────

    def recognize_image_advanced(self, image_path: str) -> dict:
        """
        增强识别：返回识别结果 + 质量报告 + 版面信息
        """
        slog.info("开始增强识别", path=os.path.basename(image_path))

        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        quality = assess_image_quality(img)
        layout = layout_analysis(img)
        results = self.recognize_image(image_path)

        enhanced = {
            "results": results,
            "quality": quality,
            "layout": layout,
            "full_text": self.get_full_text(results),
            "low_confidence": self.get_low_confidence_items(results),
        }
        slog.info("增强识别完成", path=os.path.basename(image_path),
                  texts=len(results), overall_quality=f"{quality.overall_quality:.2f}")
        return enhanced

    def analyze_layout(self, image_path: str) -> dict:
        """对图像进行版面分析"""
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")
        return layout_analysis(img)

    def assess_image_quality(self, image_path: str) -> ImageQualityReport:
        """评估图像质量"""
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")
        return assess_image_quality(img)

    def post_correct(self, results: list[dict]) -> list[dict]:
        """对 OCR 结果进行后校正"""
        return OCRPostCorrector.correct_results(results)

    def dewarp_image(self, image_path: str, aggressive: bool = True,
                     output_path: str | None = None) -> np.ndarray:
        """对图像进行去畸变处理"""
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        dewarped = dewarp_document(img, aggressive=aggressive)

        if output_path:
            ext = os.path.splitext(output_path)[1]
            cv2.imencode(ext, dewarped)[1].tofile(output_path)
            slog.info("去畸变图像已保存", path=output_path)

        return dewarped

    def binarize_image(self, image_path: str, method: str = "auto",
                       output_path: str | None = None) -> np.ndarray:
        """对图像进行自适应二值化"""
        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        binary = adaptive_binarize(img, method=method)

        if output_path:
            ext = os.path.splitext(output_path)[1]
            cv2.imencode(ext, binary)[1].tofile(output_path)
            slog.info("二值化图像已保存", path=output_path, method=method)

        return binary

    # ── 增强中文识别 API ────────────────────────────────────

    def recognize_image_with_segmentation(self, image_path: str) -> list[dict]:
        """
        增强识别：对低置信度区域进行字符级分割重识别
        """
        if not self._initialized:
            self.initialize()

        if self.ocr is None:
            raise RuntimeError("OCR 引擎初始化失败")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片不存在: {image_path}")

        img_array = np.fromfile(image_path, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"无法读取图片: {image_path}")

        results = self.recognize_image(image_path)
        if not results:
            return results

        enhanced_results = []
        reprocess_count = 0

        for item in results:
            if item["confidence"] >= 0.6:
                enhanced_results.append(item)
                continue

            bbox = item["bbox"]
            try:
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                x1 = max(0, int(min(xs)) - 5)
                y1 = max(0, int(min(ys)) - 5)
                x2 = min(img.shape[1], int(max(xs)) + 5)
                y2 = min(img.shape[0], int(max(ys)) + 5)

                sub_img = img[y1:y2, x1:x2].copy()
                if sub_img.size == 0:
                    enhanced_results.append(item)
                    continue

                sub_img = self._aggressive_preprocess(sub_img)
                sub_result = self.ocr(sub_img)
                if sub_result and sub_result.txts:
                    best_idx = int(np.argmax(sub_result.scores))
                    new_conf = sub_result.scores[best_idx]
                    new_text = sub_result.txts[best_idx]
                    new_bbox = sub_result.boxes[best_idx]

                    mapped_bbox = []
                    for pt in new_bbox:
                        mapped_bbox.append([pt[0] + x1, pt[1] + y1])

                    enhanced_results.append({
                        "text": new_text,
                        "confidence": max(new_conf, item["confidence"]),
                        "bbox": mapped_bbox,
                        "segmentation_reprocessed": True,
                    })
                    reprocess_count += 1
                else:
                    enhanced_results.append(item)
            except Exception as e:
                slog.warning("子区域重识别失败，保留原始结果",
                             error=str(e), text=item["text"][:20])
                enhanced_results.append(item)

        slog.info("字符级分割重识别完成",
                  total=len(results), reprocessed=reprocess_count)
        return enhanced_results

    @staticmethod
    def _aggressive_preprocess(img: np.ndarray) -> np.ndarray:
        """激进预处理：用于低置信度区域的二次识别"""
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel = lab[:, :, 0]
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        lab[:, :, 0] = clahe.apply(l_channel)
        img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binary = cv2.dilate(binary, kernel, iterations=1)

        img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        return img

    def recognize_image_file(self, image_path: str) -> list[dict]:
        """直接对图片文件进行 OCR 识别（支持多种图片格式）"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图片文件不存在: {image_path}")

        supported_formats = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in supported_formats:
            raise ValueError(
                f"不支持的图片格式: {ext}，"
                f"支持的格式: {', '.join(sorted(supported_formats))}"
            )

        slog.info("开始图片文件 OCR 识别",
                  path=os.path.basename(image_path), format=ext)

        results = self.recognize_image(image_path)

        slog.info("图片文件 OCR 识别完成",
                  path=os.path.basename(image_path), texts=len(results))
        return results

    def boost_confidence_with_context(self, results: list[dict], full_text: str) -> list[dict]:
        """基于上下文提升低置信度结果的置信度"""
        import re

        boosted_results = []
        boost_count = 0

        for item in results:
            new_item = dict(item)
            conf = item["confidence"]

            if conf < 0.8:
                text = item["text"]
                boost_amount = 0.0

                amount_keywords = ["¥", "￥", "$", "元", "万", "千元", "百元", "角", "分"]
                amount_pattern = re.compile(r'[¥￥$]\s*\d|[\d,]+\.\d{2}\s*元|\d+万')
                if any(kw in text for kw in amount_keywords) or amount_pattern.search(text):
                    boost_amount = max(boost_amount, 0.15)
                text_pos = full_text.find(text)
                if text_pos >= 0:
                    context_before = full_text[max(0, text_pos - 10):text_pos]
                    context_after = full_text[text_pos + len(text):text_pos + len(text) + 10]
                    for kw in amount_keywords:
                        if kw in context_before or kw in context_after:
                            boost_amount = max(boost_amount, 0.1)
                            break

                date_keywords = ["年", "月", "日"]
                date_pattern = re.compile(r'\d{4}\s*年|\d{1,2}\s*月|\d{1,2}\s*日|\d{4}[-/]\d{1,2}[-/]\d{1,2}')
                if any(kw in text for kw in date_keywords) or date_pattern.search(text):
                    boost_amount = max(boost_amount, 0.15)
                if text_pos >= 0:
                    context_window = full_text[max(0, text_pos - 15):text_pos + len(text) + 15]
                    if date_pattern.search(context_window):
                        boost_amount = max(boost_amount, 0.1)

                number_pattern = re.compile(r'(?:No\.|编号|第\s*\d+\s*号|字\s*第\s*\d+)')
                if number_pattern.search(text):
                    boost_amount = max(boost_amount, 0.1)

                percent_pattern = re.compile(r'\d+\.?\d*\s*[%％]|百分之')
                if percent_pattern.search(text):
                    boost_amount = max(boost_amount, 0.1)

                if boost_amount > 0:
                    new_item["confidence"] = min(conf + boost_amount, 0.95)
                    new_item["confidence_boosted"] = boost_amount
                    boost_count += 1

            boosted_results.append(new_item)

        slog.info("上下文置信度提升完成",
                  total=len(results), boosted=boost_count)
        return boosted_results
