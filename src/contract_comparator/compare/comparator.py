"""
字段比对引擎
对 Word 和 PDF 提取的字段进行标准化比对
"""
import re
from contract_comparator.config import COMPARATOR_CONFIG


class Comparator:
    """字段比对引擎"""
    
    def __init__(self):
        self.number_tolerance = COMPARATOR_CONFIG["number_tolerance"]
        self.number_rel_tolerance = COMPARATOR_CONFIG["number_rel_tolerance"]
        self.similarity_threshold = COMPARATOR_CONFIG["similarity_threshold"]

    def _is_close(self, a: float, b: float) -> bool:
        """数值接近判定：相对容差 + 绝对下限，二者取大。

        解决写死绝对容差 0.01 的两类问题：
        - 大金额：¥1,000,000.00 与 ¥1,000,000.01 仅差 1 分，绝对容差会误报为差异；
          相对容差（默认 1e-5）可吸收此类舍入噪声。
        - 小金额/零值：相对项趋零，由绝对下限 number_tolerance(0.01) 兜底，避免误匹配。
        """
        abs_diff = abs(a - b)
        rel_threshold = self.number_rel_tolerance * max(abs(a), abs(b))
        return abs_diff <= max(rel_threshold, self.number_tolerance)

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        """关键词归一化（去除标点、空格、统一大小写）"""
        if not keyword:
            return ""
        # 去除标点符号和空格
        normalized = re.sub(r'[^\w\u4e00-\u9fff]', '', keyword)
        return normalized.lower()
    
    def compare(self, word_fields: dict, pdf_fields: dict) -> dict:
        """
        执行字段级比对（防御性编程：处理缺失字段）
        
        Args:
            word_fields: Word 文档提取的字段
            pdf_fields: PDF 扫描件提取的字段
        
        Returns:
            比对结果
        """
        # 防御性读取：字段缺失时使用空列表兜底，避免 KeyError
        wn = word_fields.get("numbers", [])
        pn = pdf_fields.get("numbers", [])
        wd = word_fields.get("dates", [])
        pd = pdf_fields.get("dates", [])
        waw = word_fields.get("amounts_words", [])
        paw = pdf_fields.get("amounts_words", [])
        wad = word_fields.get("amounts_digits", [])
        pad = pdf_fields.get("amounts_digits", [])
        wpct = word_fields.get("percentages", [])
        ppct = pdf_fields.get("percentages", [])

        return {
            "numbers": self.compare_numbers(wn, pn),
            "dates": self.compare_dates(wd, pd),
            "amounts_words": self.compare_amounts_words(waw, paw),
            "amounts_digits": self.compare_amounts_digits(wad, pad),
            "percentages": self.compare_percentages(wpct, ppct),
        }
    
    def compare_numbers(self, word_nums: list, pdf_nums: list) -> dict:
        """
        比对数字（基于数值精确匹配 + 上下文辅助）
        
        匹配策略：
        1. 精确匹配：数值完全相同
        2. 容差匹配：数值接近 + 上下文关键词重叠
        """
        matched = []
        missing = []
        extra = []
        pdf_matched_indices = set()
        
        for i, wn in enumerate(word_nums):
            found = False
            
            for j, pn in enumerate(pdf_nums):
                if j in pdf_matched_indices:
                    continue
                
                # 策略 1：数值完全相同（优先）
                if wn["normalized"] == pn["normalized"]:
                    matched.append({"word": wn, "pdf": pn})
                    pdf_matched_indices.add(j)
                    found = True
                    break
                
                # 策略 2：数值接近 + 上下文有共同关键词
                if self._is_close(wn["normalized"], pn["normalized"]):
                    wn_ctx = wn.get("context", "")
                    pn_ctx = pn.get("context", "")
                    
                    # 提取上下文中的关键词（中文词，2字以上）
                    wn_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', wn_ctx))
                    pn_keywords = set(re.findall(r'[\u4e00-\u9fff]{2,}', pn_ctx))
                    
                    # 如果有共同关键词，认为是匹配
                    common = wn_keywords & pn_keywords
                    if common:
                        matched.append({"word": wn, "pdf": pn})
                        pdf_matched_indices.add(j)
                        found = True
                        break
            
            if not found:
                missing.append(wn)
        
        # 找出 PDF 中多出的
        for j, pn in enumerate(pdf_nums):
            if j not in pdf_matched_indices:
                extra.append(pn)
        
        return {
            "matched": matched,
            "missing_in_pdf": missing,
            "extra_in_pdf": extra,
            "has_diff": len(missing) > 0 or len(extra) > 0,
        }
    
    def compare_dates(self, word_dates: list, pdf_dates: list) -> dict:
        """
        比对日期
        
        Returns:
            {
                "matched": [...],
                "missing_in_pdf": [...],
                "extra_in_pdf": [...],
            }
        """
        word_set = {d["normalized"] for d in word_dates}
        pdf_set = {d["normalized"] for d in pdf_dates}
        
        matched = []
        missing = []
        extra = []
        
        for wd in word_dates:
            if wd["normalized"] in pdf_set:
                matched.append(wd)
            else:
                missing.append(wd)
        
        for pd_item in pdf_dates:
            if pd_item["normalized"] not in word_set:
                extra.append(pd_item)
        
        return {
            "matched": matched,
            "missing_in_pdf": missing,
            "extra_in_pdf": extra,
            "has_diff": len(missing) > 0 or len(extra) > 0,
        }
    
    def compare_amounts_words(self, word_amounts: list, pdf_amounts: list) -> dict:
        """
        比对大写金额（字符串精确匹配）
        """
        word_set = {a["raw"] for a in word_amounts}
        pdf_set = {a["raw"] for a in pdf_amounts}
        
        matched = []
        missing = []
        extra = []
        
        for wa in word_amounts:
            if wa["raw"] in pdf_set:
                matched.append(wa)
            else:
                missing.append(wa)
        
        for pa in pdf_amounts:
            if pa["raw"] not in word_set:
                extra.append(pa)
        
        return {
            "matched": matched,
            "missing_in_pdf": missing,
            "extra_in_pdf": extra,
            "has_diff": len(missing) > 0 or len(extra) > 0,
        }
    
    def compare_amounts_digits(self, word_amounts: list, pdf_amounts: list) -> dict:
        """
        比对金额数字（关键词归一化 + 短语级匹配）
        
        匹配策略：
        1. 优先匹配：关键词归一化后相同 + 数字容差内
        2. 短语匹配：短语中包含相同核心词 + 数字相同
        3. 数值匹配：数字相同 + 上下文关键词相似
        """
        matched = []
        missing = []
        extra = []
        pdf_matched_indices = set()
        
        for i, wa in enumerate(word_amounts):
            wa_kw = self.normalize_keyword(wa.get("keyword", ""))
            wa_phrase = self.normalize_keyword(wa.get("phrase", ""))
            found = False
            
            for j, pa in enumerate(pdf_amounts):
                if j in pdf_matched_indices:
                    continue
                    
                pa_kw = self.normalize_keyword(pa.get("keyword", ""))
                pa_phrase = self.normalize_keyword(pa.get("phrase", ""))
                
                # 策略 1：关键词相同 + 数字接近
                if wa_kw and pa_kw and wa_kw == pa_kw:
                    if self._is_close(wa["normalized"], pa["normalized"]):
                        matched.append({"word": wa, "pdf": pa})
                        pdf_matched_indices.add(j)
                        found = True
                        break
                
                # 策略 2：短语中包含相同核心数字 + 数字相同
                if self._is_close(wa["normalized"], pa["normalized"]):
                    # 检查短语中是否有共同的关键词
                    wa_raw = str(wa["normalized"])
                    pa_raw = str(pa["normalized"])
                    if wa_raw == pa_raw:
                        # 数字完全相同，检查上下文是否相关
                        wa_ctx = self.normalize_keyword(wa.get("context", ""))
                        pa_ctx = self.normalize_keyword(pa.get("context", ""))
                        # 如果上下文有重叠关键词
                        if any(kw in wa_ctx and kw in pa_ctx 
                               for kw in ['费用', '金额', '总计', '包干', '违约', '赔偿']):
                            matched.append({"word": wa, "pdf": pa})
                            pdf_matched_indices.add(j)
                            found = True
                            break
            
            if not found:
                missing.append(wa)
        
        # 找出 PDF 中多出的
        for j, pa in enumerate(pdf_amounts):
            if j not in pdf_matched_indices:
                extra.append(pa)
        
        return {
            "matched": matched,
            "missing_in_pdf": missing,
            "extra_in_pdf": extra,
            "has_diff": len(missing) > 0 or len(extra) > 0,
        }
    
    def compare_percentages(self, word_pcts: list, pdf_pcts: list) -> dict:
        """
        比对百分比
        """
        matched = []
        missing = []
        extra = []
        
        for wp in word_pcts:
            found = False
            for pp in pdf_pcts:
                if abs(wp["normalized"] - pp["normalized"]) < 0.001:
                    matched.append({"word": wp, "pdf": pp})
                    found = True
                    break
            if not found:
                missing.append(wp)
        
        for pp in pdf_pcts:
            if not any(
                abs(pp["normalized"] - wp["normalized"]) < 0.001
                for wp in word_pcts
            ):
                extra.append(pp)
        
        return {
            "matched": matched,
            "missing_in_pdf": missing,
            "extra_in_pdf": extra,
            "has_diff": len(missing) > 0 or len(extra) > 0,
        }
    
    def get_summary(self, comparison_result: dict) -> dict:
        """
        获取比对摘要
        
        Returns:
            {
                "total_diffs": 差异总数,
                "has_critical_diff": 是否有严重差异,
                "diff_details": [...]
            }
        """
        diffs = []
        
        # 检查各类差异
        if comparison_result["numbers"]["has_diff"]:
            diffs.append({
                "type": "数字",
                "missing": len(comparison_result["numbers"]["missing_in_pdf"]),
                "extra": len(comparison_result["numbers"]["extra_in_pdf"]),
            })
        
        if comparison_result["dates"]["has_diff"]:
            diffs.append({
                "type": "日期",
                "missing": len(comparison_result["dates"]["missing_in_pdf"]),
                "extra": len(comparison_result["dates"]["extra_in_pdf"]),
            })
        
        if comparison_result["amounts_words"]["has_diff"]:
            diffs.append({
                "type": "大写金额",
                "missing": len(comparison_result["amounts_words"]["missing_in_pdf"]),
                "extra": len(comparison_result["amounts_words"]["extra_in_pdf"]),
            })
        
        if comparison_result["amounts_digits"]["has_diff"]:
            diffs.append({
                "type": "金额数字",
                "missing": len(comparison_result["amounts_digits"]["missing_in_pdf"]),
                "extra": len(comparison_result["amounts_digits"]["extra_in_pdf"]),
            })
        
        if comparison_result["percentages"]["has_diff"]:
            diffs.append({
                "type": "百分比",
                "missing": len(comparison_result["percentages"]["missing_in_pdf"]),
                "extra": len(comparison_result["percentages"]["extra_in_pdf"]),
            })
        
        total_diffs = sum(d["missing"] + d["extra"] for d in diffs)
        has_critical = any(d["type"] in ["大写金额", "金额数字"] for d in diffs)
        
        return {
            "total_diffs": total_diffs,
            "has_critical_diff": has_critical,
            "diff_details": diffs,
        }
