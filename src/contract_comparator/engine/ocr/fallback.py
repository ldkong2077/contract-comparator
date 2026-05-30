"""
多引擎回退 — RapidOCR → EasyOCR → Tesseract
"""

import logging

import cv2
import numpy as np

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class FallbackEngine:
    """OCR 回退引擎：RapidOCR → EasyOCR → Tesseract"""

    @staticmethod
    def try_easyocr(img_input) -> list[dict]:
        """
        尝试 EasyOCR 识别
        注意：EasyOCR 首次运行会下载模型（~200MB）
        """
        try:
            import easyocr
            slog.info("启用 EasyOCR 回退引擎")
            reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
            if isinstance(img_input, np.ndarray):
                results_easy = reader.readtext(img_input)
            else:
                results_easy = reader.readtext(img_input)

            parsed = []
            for bbox, text, conf in results_easy:
                parsed.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": bbox if isinstance(bbox, list) else bbox.tolist(),
                })
            slog.info("EasyOCR 回退完成", texts=len(parsed))
            return parsed
        except ImportError:
            slog.warning("EasyOCR 未安装，跳过回退")
            return []
        except Exception as e:
            slog.error("EasyOCR 回退异常", error=str(e))
            return []

    @staticmethod
    def try_tesseract(img_input) -> list[dict]:
        """
        尝试 Tesseract OCR 识别
        注意：需系统安装 tesseract 并配置中文语言包
        """
        try:
            import pytesseract
            slog.info("启用 Tesseract 回退引擎")

            if isinstance(img_input, np.ndarray):
                pil_img = img_input
            else:
                img_array = np.fromfile(img_input, dtype=np.uint8)
                pil_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

            data = pytesseract.image_to_data(pil_img, lang="chi_sim+eng",
                                              output_type=pytesseract.Output.DICT)

            parsed = []
            for i in range(len(data["text"])):
                text = (data["text"][i] or "").strip()
                conf = int(data["conf"][i]) / 100.0 if data["conf"][i] != "-1" else 0.0
                if text and conf >= 0:
                    x, y, bw, bh = (data["left"][i], data["top"][i],
                                    data["width"][i], data["height"][i])
                    parsed.append({
                        "text": text,
                        "confidence": conf,
                        "bbox": [[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]],
                    })
            slog.info("Tesseract 回退完成", texts=len(parsed))
            return parsed
        except ImportError:
            slog.warning("pytesseract 未安装，跳过 Tesseract 回退")
            return []
        except Exception as e:
            slog.error("Tesseract 回退异常", error=str(e))
            return []

    @staticmethod
    def fallback_recognize(img_input, preferred_order: list[str] | None = None) -> list[dict]:
        """
        按优先级尝试回退引擎

        Args:
            img_input: 图像路径或 numpy array
            preferred_order: 引擎优先级列表，默认 ["easyocr", "tesseract"]

        Returns:
            识别结果列表（第一个成功的结果）
        """
        if preferred_order is None:
            preferred_order = ["easyocr", "tesseract"]

        for engine_name in preferred_order:
            slog.info("尝试回退引擎", engine=engine_name)
            if engine_name == "easyocr":
                results = FallbackEngine.try_easyocr(img_input)
            elif engine_name == "tesseract":
                results = FallbackEngine.try_tesseract(img_input)
            else:
                slog.warning("未知回退引擎", engine=engine_name)
                continue

            if results:
                slog.info("回退引擎成功", engine=engine_name, texts=len(results))
                return results

        slog.error("所有回退引擎均失败")
        return []
