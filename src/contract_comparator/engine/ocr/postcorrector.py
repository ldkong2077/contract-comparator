"""
OCR 后校正 — 中文常见 OCR 错误模式校正
"""

import logging

from contract_comparator.engine.ocr.logger import StructuredLogger

logger = logging.getLogger(__name__)
slog = StructuredLogger(logger)


# 形近字混淆对
_SIMILAR_CHARS = {
    "已": "己", "己": "已",
    "未": "末", "末": "未",
    "干": "千", "千": "干",
    "土": "士", "士": "土",
    "曰": "日", "日": "曰",
    "人": "入", "入": "人",
    "大": "太", "太": "大",
    "夭": "天", "天": "夭",
    "乌": "鸟", "鸟": "乌",
    "免": "兔", "兔": "免",
    "酒": "洒", "洒": "酒",
    "候": "侯", "侯": "候",
    "拨": "拔", "拔": "拨",
    "刺": "剌", "剌": "刺",
    "崇": "祟", "祟": "崇",
    "盲": "育", "育": "盲",
    "汩": "汨", "汨": "汩",
    "茶": "荼", "荼": "茶",
    "赢": "羸", "羸": "赢",
    "辨": "辩", "辩": "辨",
    "粱": "梁", "梁": "粱",
    "栗": "粟", "粟": "栗",
    "陪": "赔", "赔": "陪",
    "竞": "竟", "竟": "竞",
    "历": "厉", "厉": "历",
    "密": "蜜", "蜜": "密",
    "板": "扳", "扳": "板",
    "模": "摸", "摸": "模",
    "稿": "搞", "搞": "稿",
    "码": "玛", "玛": "码",
    "狠": "狼", "狼": "狠",
    "根": "跟", "跟": "根",
    "性": "姓", "姓": "性",
    "纪": "记", "记": "纪",
    "徒": "徙", "徙": "徒",
    "裁": "栽", "栽": "裁",
    "载": "戴", "戴": "载",
}

# 常见数字类 OCR 错误
_DIGIT_CORRECTIONS = {
    "0": "O", "O": "0",
    "1": "l", "l": "1",
    "6": "b", "b": "6",
    "8": "B", "B": "8",
    "9": "g", "g": "9",
}


def _context_aware_correct(word: str, confidence: float, context_window: tuple[str, str, str] = ("", "", "")) -> str:
    """
    基于上下文的单字后校正
    context_window: (前一字, 当前字, 后一字)
    """
    prev_char, curr_char, next_char = context_window

    # 只在低置信度时尝试校正
    if confidence >= 0.85:
        return word

    # 形近字替换
    if word in _SIMILAR_CHARS:
        return _SIMILAR_CHARS[word]

    return word


class OCRPostCorrector:
    """OCR 后校正器：将常见的 OCR 识别错误模式进行校正"""

    # 常见中文 OCR 易错词组（整体替换）
    _COMMON_PHRASE_FIXES = {
        "己经": "已经",
        "未来": "未来",
        "千部": "干部",
        "土兵": "士兵",
        "大阳": "太阳",
        "鸟云": "乌云",
        "免子": "兔子",
        "酒水": "洒水",
        "拔款": "拨款",
        "侯选": "候选",
        "祟高": "崇高",
        "育目": "盲目",
        "荼叶": "茶叶",
        "羸利": "盈利",
        "辩别": "辨别",
        "梁食": "粮食",
        "粟米": "粟米",
        "赔偿": "赔偿",
        "竟争": "竞争",
        "厉史": "历史",
        "蜜封": "密封",
        "扳权": "版权",
        "摸型": "模型",
        "搞件": "稿件",
        "玛头": "码头",
        "狼心": "狠心",
        "跟本": "根本",
        "姓质": "性质",
        "记律": "纪律",
        "徙弟": "徒弟",
        "栽判": "裁判",
        "戴重": "载重",
    }

    @staticmethod
    def correct_text(text: str, confidence: float = 0.5) -> tuple[str, bool]:
        """
        对单段文本进行后校正

        Args:
            text: 原始识别文本
            confidence: 该段文本的置信度

        Returns:
            (校正后文本, 是否修改)
        """
        if confidence >= 0.85 or len(text) < 2:
            return text, False

        corrected = text
        modified = False

        # 1. 短语级替换
        for wrong, right in OCRPostCorrector._COMMON_PHRASE_FIXES.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                modified = True

        # 2. 低置信度单字替换（保守策略）
        if confidence < 0.6:
            chars = list(corrected)
            replaced_any = False
            for i, ch in enumerate(chars):
                if ch in _SIMILAR_CHARS:
                    candidate = _SIMILAR_CHARS[ch]
                    context_before = ''.join(chars[max(0,i-3):i])
                    context_after = ''.join(chars[i+1:min(len(chars),i+4)])

                    is_amount_related = any(kw in (context_before + context_after)
                        for kw in ['元', '万', '千', '百', '角', '分', '¥', '￥', '$'])
                    is_digit_related = (i > 0 and chars[i-1].isdigit()) or \
                                      (i < len(chars)-1 and chars[i+1].isdigit())

                    if is_amount_related or is_digit_related:
                        chars[i] = candidate
                        replaced_any = True
            if replaced_any:
                corrected = "".join(chars)
                modified = True

        if modified:
            slog.debug("文本后校正", original=text[:20], corrected=corrected[:20])

        return corrected, modified

    @staticmethod
    def correct_results(results: list[dict]) -> list[dict]:
        """
        对整批 OCR 结果进行后校正

        Args:
            results: OCR 识别结果列表

        Returns:
            校正后的结果列表
        """
        total_corrected = 0
        new_results = []
        for item in results:
            text = item["text"]
            conf = item["confidence"]
            corrected_text, modified = OCRPostCorrector.correct_text(text, conf)
            new_item = dict(item)
            new_item["text"] = corrected_text
            new_item["post_corrected"] = modified
            new_results.append(new_item)
            if modified:
                total_corrected += 1

        slog.info("后校正完成", total=len(results), corrected=total_corrected)
        return new_results
