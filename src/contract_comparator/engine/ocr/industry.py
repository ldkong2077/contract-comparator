"""
行业字段识别器 — 从 OCR 结果中提取行业特定字段
"""

import logging
import re as _re

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


class IndustryFieldRecognizer:
    """
    行业特定字段识别器

    根据不同行业的关键词字典，从 OCR 识别结果中提取结构化字段。
    支持行业：general（通用）、construction（工程建设）、leasing（租赁）、
    procurement（采购）、labor（劳务/劳动合同）
    """

    _INDUSTRY_KEYWORDS: dict[str, list[str]] = {
        "general": [
            "甲方", "乙方", "合同编号", "签订日期", "合同金额",
            "有效期", "地址", "联系人", "电话", "传真",
        ],
        "construction": [
            "工程名称", "施工单位", "监理单位", "工期", "质量标准",
            "验收标准", "安全文明施工费", "暂列金额",
        ],
        "leasing": [
            "出租方", "承租方", "租赁物", "租赁期限", "租金",
            "押金", "违约金", "提前解约",
        ],
        "procurement": [
            "供方", "需方", "产品名称", "规格型号", "数量",
            "单价", "交货期", "质保期",
        ],
        "labor": [
            "用人单位", "劳动者", "劳动期限", "试用期", "岗位",
            "工资", "社保", "解除条件",
        ],
    }

    def __init__(self, industry: str = "general"):
        supported = list(self._INDUSTRY_KEYWORDS.keys())
        if industry not in supported:
            raise ValueError(
                f"不支持的行业类型: {industry}，"
                f"支持的行业: {', '.join(supported)}"
            )
        self.industry = industry
        self.keywords = self._INDUSTRY_KEYWORDS[industry]
        slog.info("行业字段识别器初始化", industry=industry,
                  keywords_count=len(self.keywords))

    def recognize_fields(self, ocr_results: list[dict]) -> dict:
        fields = []
        sorted_results = sorted(ocr_results, key=lambda x: (x["bbox"][0][1], x["bbox"][0][0]))

        for keyword in self.keywords:
            best_match = None
            best_confidence = 0.0
            best_value = ""
            best_bbox = []

            for i, item in enumerate(sorted_results):
                text = item["text"]
                conf = item["confidence"]

                if keyword in text:
                    value = self._extract_value_from_text(keyword, text)
                    if not value:
                        value, val_conf, val_bbox = self._find_adjacent_value(
                            item, sorted_results, i
                        )
                        conf = (conf + val_conf) / 2 if val_conf > 0 else conf
                        best_bbox = val_bbox if val_bbox else item["bbox"]
                    else:
                        best_bbox = item["bbox"]

                    if conf > best_confidence:
                        best_match = keyword
                        best_confidence = conf
                        best_value = value
                        best_bbox = best_bbox
                    continue

                similarity = self._calc_similarity(keyword, text)
                if similarity >= 0.7 and conf > best_confidence:
                    value = self._extract_value_from_text(keyword, text)
                    if not value:
                        value, val_conf, val_bbox = self._find_adjacent_value(
                            item, sorted_results, i
                        )
                        conf = (conf + val_conf) / 2 if val_conf > 0 else conf * similarity
                        best_bbox = val_bbox if val_bbox else item["bbox"]
                    else:
                        best_bbox = item["bbox"]
                        conf *= similarity

                    best_match = keyword
                    best_confidence = conf
                    best_value = value

            if best_match:
                fields.append({
                    "name": best_match,
                    "value": best_value,
                    "confidence": round(best_confidence, 4),
                    "bbox": best_bbox,
                })

        slog.info("行业字段提取完成", industry=self.industry,
                  keywords=len(self.keywords), fields_found=len(fields))

        return {
            "industry": self.industry,
            "fields": fields,
        }

    @staticmethod
    def _extract_value_from_text(keyword: str, text: str) -> str:
        pattern = _re.compile(_re.escape(keyword) + r'\s*[：:=＝]\s*(.+)')
        match = pattern.search(text)
        if match:
            return match.group(1).strip()

        pattern2 = _re.compile(_re.escape(keyword) + r'\s+(\S+)')
        match2 = pattern2.search(text)
        if match2:
            return match2.group(1).strip()

        return ""

    @staticmethod
    def _find_adjacent_value(item: dict, sorted_results: list[dict],
                             current_idx: int) -> tuple[str, float, list]:
        curr_bbox = item["bbox"]
        curr_y = curr_bbox[0][1]
        curr_x_right = max(pt[0] for pt in curr_bbox)
        curr_height = max(pt[1] for pt in curr_bbox) - min(pt[1] for pt in curr_bbox)

        best_value = ""
        best_conf = 0.0
        best_bbox = []
        min_gap = float('inf')

        for j, other in enumerate(sorted_results):
            if j == current_idx:
                continue
            other_bbox = other["bbox"]
            other_y = other_bbox[0][1]
            other_x_left = min(pt[0] for pt in other_bbox)

            if abs(other_y - curr_y) <= max(curr_height * 0.5, 10):
                gap = other_x_left - curr_x_right
                if 0 <= gap < min_gap and gap < curr_height * 3:
                    min_gap = gap
                    best_value = other["text"]
                    best_conf = other["confidence"]
                    best_bbox = other["bbox"]

        return best_value, best_conf, best_bbox

    @staticmethod
    def _calc_similarity(s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        len1, len2 = len(s1), len(s2)
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1]
                else:
                    dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])
        max_len = max(len1, len2)
        return 1.0 - dp[len1][len2] / max_len
