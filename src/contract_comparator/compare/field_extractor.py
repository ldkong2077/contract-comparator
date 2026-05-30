"""
关键字段抽取模块
从文本中提取金额、日期、数字等核心字段
"""
import re
import unicodedata
from datetime import datetime
from contract_comparator.config import FIELD_CONFIG


class FieldExtractor:
    """字段抽取器"""

    def __init__(self):
        self.number_patterns = FIELD_CONFIG["number_patterns"]
        self.date_patterns = FIELD_CONFIG["date_patterns"]
        self.amount_word_patterns = FIELD_CONFIG["amount_word_patterns"]
        self.amount_keywords = FIELD_CONFIG["amount_keywords"]

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        全角→半角归一化（合同比对核心）

        处理：
        - ¥（半角 U+00A5）↔ ￥（全角 U+FFE5）
        - ％（全角百分号）→ %（半角）
        - ：（全角冒号）→ :（半角）
        - （）（全角括号）→ ()（半角）
        - 空格归一化
        """
        # 货币符号统一
        text = text.replace('\uffe5', '\u00a5')  # ￥ → ¥
        # 百分号统一
        text = text.replace('\uff05', '%')
        # 冒号统一
        text = text.replace('\uff1a', ':')
        # 括号统一
        text = text.replace('\uff08', '(').replace('\uff09', ')')
        # 逗号统一（千分位）
        text = text.replace('\uff0c', ',')
        # 句号统一
        text = text.replace('\u3002', '.')
        # 全角数字→半角数字
        text = unicodedata.normalize('NFKC', text)
        return text

    def extract_all(self, text: str, source: str = "unknown") -> dict:
        """
        从文本中提取所有关键字段

        Args:
            text: 输入文本
            source: 来源标识（"word" 或 "pdf"）

        Returns:
            字段字典
        """
        # 先做全角→半角归一化
        text = self.normalize_text(text)

        return {
            "source": source,
            "numbers": self.extract_numbers(text),
            "dates": self.extract_dates(text),
            "amounts_words": self.extract_amount_words(text),
            "amounts_digits": self.extract_amount_digits(text),
            "percentages": self.extract_percentages(text),
            "party_names": self.extract_party_names(text),
            "contract_numbers": self.extract_contract_numbers(text),
            "clauses": self.extract_clauses(text),
            "legal_terms": self.extract_legal_terms(text),
            "contact_info": self.extract_contact_info(text),
            "terms": self.extract_terms(text),
        }

    def extract_numbers(self, text: str) -> list[dict]:
        """
        提取有意义的数字（排除地块编号、序号、银行账号、印章编码等干扰项）

        过滤规则：
        - 排除 2 位以下纯数字（如 05、02 地块编号）
        - 排除 1.00 这种纯格式数字
        - 排除 > 12 位的超长数字（银行账号、身份证号）
        - 排除字母相邻的数字（印章编码如 B621JE）
        - 排除"第X条"等条款编号（前后有"第"和"条"）
        - 排除"附件X"、"图X"、"表X"等序号
        - 排除纯1位小数的格式数字（如1.50, 2.30）
        - 只保留 3~12 位的数字

        Returns:
            [{"raw": "100000", "normalized": 100000.0, "context": "..."}, ...]
        """
        results = []
        # 匹配连续数字（含小数、千分位逗号）
        pattern = r'(\d+(?:,\d{3})*(?:\.\d+)?)'

        for match in re.finditer(pattern, text):
            raw = match.group(1)
            num_clean = raw.replace(',', '').replace('.', '')

            # 过滤规则：
            # 1. 排除 2 位以下数字（地块编号如 05、02、08）
            if len(num_clean) < 3:
                continue
            # 2. 排除 > 12 位的超长数字（银行账号、身份证号）
            if len(num_clean) > 12:
                continue

            # 3. 排除字母相邻的数字（印章编码如 B621JE、A123B）
            # 只检查 ASCII 字母（a-zA-Z），中文等 Unicode 字符不排除
            before_char = text[match.start() - 1] if match.start() > 0 else ''
            after_char = text[match.end()] if match.end() < len(text) else ''
            if before_char.isascii() and before_char.isalpha() or after_char.isascii() and after_char.isalpha():
                continue

            # 4. 排除 "1.00" 这种格式数字（修复 Bug：用原始值判断）
            try:
                val = float(raw.replace(',', ''))
                if val == 1.0 and '.' in raw:
                    continue
            except ValueError:
                pass

            # 5. 排除"第X条"等条款编号（如"第3条"、"第12条"）
            if before_char == '第' and any(c in text[match.end():match.end()+2] for c in ['条', '款', '项']):
                continue

            # 6. 排除"附件X"、"图X"、"表X"、"章X"等序号
            if before_char in ['附', '图', '表', '章', '节', '号'] or \
               (after_char in ['号', '条'] and text[match.start()-1:match.start()] in ['第', '条']):
                continue

            # 7. 排除纯1位小数的格式数字（如1.50, 2.30）但保留正常金额格式
            # 如果小数部分只有1位且整数部分只有1位，跳过（可能是页码或比例）
            decimal_part = raw.split('.')[1] if '.' in raw else ''
            integer_part = raw.split('.')[0].replace(',', '')
            if len(decimal_part) == 1 and len(integer_part) <= 2 and float(raw.replace(',', '')) < 10:
                continue

            normalized = self.normalize_number(raw)
            # 获取上下文
            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": raw,
                "normalized": normalized,
                "context": context,
            })

        return results

    def extract_dates(self, text: str) -> list[dict]:
        """
        提取所有日期

        Returns:
            [{"raw": "2024年1月15日", "normalized": "2024-01-15", "context": "..."}, ...]
        """
        results = []

        for pattern in self.date_patterns:
            for match in re.finditer(pattern, text):
                raw = match.group(0)
                normalized = self.normalize_date(raw)

                if normalized:
                    start = max(0, match.start() - 20)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end].strip()

                    # 去重
                    if not any(r["normalized"] == normalized for r in results):
                        results.append({
                            "raw": raw,
                            "normalized": normalized,
                            "context": context,
                        })

        return results

    def extract_amount_words(self, text: str) -> list[dict]:
        """
        提取大写金额（严格模式，减少误识别）

        验证规则：
        - 长度 >= 4（排除单字）
        - 包含"元"或"圆"（金额单位）
        - 不能以"零"开头（无效金额）
        - 连续"零"不超过2次
        - 排除纯"零"重复（零零零零）
        - 必须包含有效数字字符（壹/贰/叁/肆/伍/陆/柒/捌/玖/拾）

        Returns:
            [{"raw": "壹拾伍万元整", "normalized": "壹拾伍万元整", "context": "..."}, ...]
        """
        results = []

        for pattern in self.amount_word_patterns:
            for match in re.finditer(pattern, text):
                raw = match.group(0)

                # 验证规则
                if not self._is_valid_chinese_amount(raw):
                    continue

                start = max(0, match.start() - 20)
                end = min(len(text), match.end() + 20)
                context = text[start:end].strip()

                results.append({
                    "raw": raw,
                    "normalized": raw,
                    "context": context,
                })

        return results

    @staticmethod
    def _is_valid_chinese_amount(text: str) -> bool:
        """
        验证中文大写金额是否有效

        规则：
        1. 必须包含"元"或"圆"（金额单位）
        2. 长度 >= 4
        3. 不能以"零"开头
        4. 连续"零"不超过2次
        5. 必须包含有效数字字符
        6. 排除纯"零"重复（零零零零...）
        """
        if len(text) < 4:
            return False
        if not any(c in text for c in ['元', '圆']):
            return False
        if text.startswith('零'):
            return False
        # 检查连续零
        if '零零零' in text or '零零零零' in text:
            return False
        # 必须包含有效数字字符（排除纯符号）
        valid_chars = set('壹贰叁肆伍陆柒捌玖拾佰仟万亿')
        if not any(c in text for c in valid_chars):
            return False
        return True

    def extract_amount_digits(self, text: str) -> list[dict]:
        """
        提取金额数字（多种合同格式兼容）

        支持的格式：
        1. ¥900000.00 / ￥900000.00         - 货币符号+数字
        2. 违约金50000元                      - 关键词+数字+元
        3. 费用为¥900000.00元                 - 关键词+为+符号+数字+元
        4. 总计费用为¥1000000.00元            - 复合关键词+数字
        5. 小计 100000.00                     - 关键词+空格+数字
        6. 总金额：100000元                    - 关键词+冒号+数字
        7. 人民币XXX元                        - 人民币+数字+元
        8. RMB XXX                           - RMB+数字
        9. 跨行金额                           - 关键词换行后紧跟数字

        过滤规则：
        - 排除 < 100 的数字（不可能是金额）
        - 排除地块编号（05-02 中的 05、02）
        - 排除银行账号（>12位）

        Returns:
            [{"raw": "900000.00", "normalized": 900000.0, "keyword": "包干费用",
              "phrase": "包干费用为¥900000.00元", "context": "..."}, ...]
        """
        results = []
        matched_ranges = []  # 记录已匹配的范围，避免重叠

        def is_valid_amount(raw: str) -> bool:
            """验证是否为有效金额数字"""
            num_clean = raw.replace(',', '').replace('.', '')
            # 至少 3 位数字
            if len(num_clean) < 3:
                return False
            # 排除超长数字（银行账号）
            if len(num_clean) > 12:
                return False
            try:
                val = float(num_clean)
                # 金额至少 >= 100
                if val < 100:
                    return False
            except ValueError:
                return False
            return True

        def overlaps_existing(start: int, end: int) -> bool:
            """检查是否与已匹配的范围重叠"""
            for ms, me in matched_ranges:
                if start < me and end > ms:
                    return True
            return False

        keyword_pattern = '|'.join(re.escape(kw) for kw in self.amount_keywords)

        # === 模式 1：关键词 + 为 + 货币符号 + 数字 + 元（优先，最精确）===
        # 费用为¥900000.00元 / 总计费用为¥1000000.00元
        pattern1 = rf'({keyword_pattern})\s*为\s*[¥＄$]?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*元'
        for match in re.finditer(pattern1, text):
            raw = match.group(2)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            keyword = match.group(1)
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": keyword,
                "phrase": phrase,
                "context": context,
            })

        # === 模式 1b：人民币 + 数字 + 元 ===
        # 人民币壹拾万元整 / 人民币100000元 / 人民币 100,000 元
        pattern1b = r'人民币\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*元'
        for match in re.finditer(pattern1b, text):
            raw = match.group(1)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": "人民币",
                "phrase": phrase,
                "context": context,
            })

        # === 模式 1c：RMB + 数字 ===
        # RMB 100000 / RMB100,000.00
        pattern1c = r'RMB\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
        for match in re.finditer(pattern1c, text):
            raw = match.group(1)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": "RMB",
                "phrase": phrase,
                "context": context,
            })

        # === 模式 2：关键词 + 数字 + 元 ===
        # 违约金50000元 / 赔偿金10000元 / 保证金5000元
        pattern2 = rf'({keyword_pattern})\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*元'
        for match in re.finditer(pattern2, text):
            raw = match.group(2)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            keyword = match.group(1)
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": keyword,
                "phrase": phrase,
                "context": context,
            })

        # === 模式 3：货币符号 + 数字（兜底，提取未被其他模式覆盖的金额）===
        # ¥900000.00 / ￥900000.00 / $1000
        pattern3 = r'([¥＄$])\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
        for match in re.finditer(pattern3, text):
            raw = match.group(2)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            normalized = self.normalize_number(raw)

            # 提取更长的上下文短语（前后各50字符）
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()

            # 提取关键词：货币符号前的词（取更长的匹配）
            keyword_start = max(0, match.start() - 30)
            keyword_context = text[keyword_start:match.start()].strip()
            # 优先取包含"费用/金额/总价"等词的短语
            kw_match = re.search(r'([\u4e00-\u9fff]*(?:费用|金额|总价|总额|合计|包干)[\u4e00-\u9fff]*)$', keyword_context)
            if not kw_match:
                # 其次取最后一个连续中文字
                kw_match = re.search(r'([\u4e00-\u9fff]+)$', keyword_context)
            keyword = kw_match.group(1) if kw_match else match.group(1)

            # 提取完整短语
            phrase_start = max(0, match.start() - 10)
            phrase_end = min(len(text), match.end() + 10)
            phrase = text[phrase_start:phrase_end].strip()

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": keyword,
                "phrase": phrase,
                "context": context,
            })

        # === 模式 4：关键词 + 冒号/空格 + 数字 ===
        # 小计 100000.00 / 合计：100000 / 总计: 50000
        pattern4 = rf'({keyword_pattern})\s*[:：]?\s+(\d+(?:,\d{3})*(?:\.\d+)?)'
        for match in re.finditer(pattern4, text):
            raw = match.group(2)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            keyword = match.group(1)
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": keyword,
                "phrase": phrase,
                "context": context,
            })

        # === 模式 5：跨行金额 — 关键词后紧跟换行和数字 ===
        # 总价
        # 1000000.00
        pattern5 = rf'({keyword_pattern})\s*[\n\r]+\s*(\d+(?:,\d{3})*(?:\.\d+)?)'
        for match in re.finditer(pattern5, text):
            raw = match.group(2)
            if not is_valid_amount(raw):
                continue
            if overlaps_existing(match.start(), match.end()):
                continue

            matched_ranges.append((match.start(), match.end()))
            keyword = match.group(1)
            normalized = self.normalize_number(raw)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()
            phrase = match.group(0)

            results.append({
                "raw": raw,
                "normalized": normalized,
                "keyword": keyword,
                "phrase": phrase,
                "context": context,
            })

        return results

    def extract_percentages(self, text: str) -> list[dict]:
        """
        提取百分比

        Returns:
            [{"raw": "5%", "normalized": 0.05, "context": "..."}, ...]
        """
        results = []
        pattern = r'(\d+(?:\.\d+)?)%'

        for match in re.finditer(pattern, text):
            raw = match.group(0)
            normalized = float(match.group(1)) / 100

            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()

            results.append({
                "raw": raw,
                "normalized": normalized,
                "context": context,
            })

        return results

    # ==================================================================
    # 新增：商业级提取维度
    # ==================================================================

    def extract_party_names(self, text: str) -> list[dict]:
        """
        提取合同当事方名称

        检测模式：
        - 甲方：XX公司 / 甲方:XX有限公司
        - 甲方（XX有限公司）/ 乙方（XX集团有限公司）
        - 甲方：XX中心 / 乙方：XX工作室
        - 支持 甲/乙/丙/丁...方

        公司名匹配规则：
        - 以"公司"、"中心"、"事务所"、"工作室"、"集团"、"厂"等结尾
        - 紧跟在"X方"标签之后

        Returns:
            [{"raw": "甲方：深圳市XX科技有限公司", "normalized": "深圳市XX科技有限公司",
              "party": "甲方", "name": "深圳市XX科技有限公司", "context": "..."}, ...]
        """
        results = []

        # 模式 1：X方[）)]?[：:] + 实体名称（冒号分隔）
        # 支持：甲方：XX公司 / 甲方):XX公司 / 甲方）：XX有限公司
        pattern1 = r'([甲乙丙丁戊己庚辛壬癸\d]+方)\s*[）)]?\s*[:：]\s*([^\n\r]{4,40}(?:公司|中心|事务所|工作室|集团|厂|处|局|行|会|院|所|部|站))'
        for match in re.finditer(pattern1, text):
            party = match.group(1)
            name = match.group(2).strip()

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0),
                "normalized": name,
                "party": party,
                "name": name,
                "context": context,
            })

        # 模式 2：X方[（(] + 实体名称[）)]（括号分隔）
        pattern2 = r'([甲乙丙丁戊己庚辛壬癸\d]+方)[（(]\s*([^\n\r]{4,40}(?:公司|中心|事务所|工作室|集团|厂|处|局|行|会|院|所|部|站))[）)]'
        for match in re.finditer(pattern2, text):
            party = match.group(1)
            name = match.group(2).strip()

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0),
                "normalized": name,
                "party": party,
                "name": name,
                "context": context,
            })

        # 模式 3：X方后紧跟空格或换行 + 公司名（无冒号无括号）
        pattern3 = r'([甲乙丙丁戊己庚辛壬癸\d]+方)\s+([^\n\r]{4,40}(?:公司|中心|事务所|工作室|集团|厂|处|局|行|会|院|所|部|站))'
        for match in re.finditer(pattern3, text):
            party = match.group(1)
            name = match.group(2).strip()

            # 排除已在模式1/2中匹配过的
            if not any(r["party"] == party and r["name"] == name for r in results):
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].strip()

                results.append({
                    "raw": match.group(0),
                    "normalized": name,
                    "party": party,
                    "name": name,
                    "context": context,
                })

        return results

    def extract_contract_numbers(self, text: str) -> list[dict]:
        """
        提取合同编号

        检测模式：
        - 合同编号：XXX-2024-001 / 合同编号:XYZ-2024-001
        - No. XXXX / No: XXXX
        - 编号：XXX-2025-A01

        Returns:
            [{"raw": "合同编号：HT-2024-001", "normalized": "HT-2024-001", "context": "..."}, ...]
        """
        results = []

        # 模式 1：合同编号[：:] + 编号内容
        pattern1 = r'合同编号\s*[:：]\s*([A-Za-z0-9\-_./]+)'
        for match in re.finditer(pattern1, text):
            num = match.group(1).strip().rstrip('.')  # 去掉末尾句号

            # 过滤太短的（如纯数字1位）
            if len(num) < 2:
                continue

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0).rstrip('.'),
                "normalized": num,
                "context": context,
            })

        # 模式 2：No. XXXX / No: XXXX
        pattern2 = r'No\.?\s*[:：]?\s*([A-Za-z0-9\-_./]+)'
        for match in re.finditer(pattern2, text, re.IGNORECASE):
            num = match.group(1).strip()
            # 过滤太短的（如 No. 1）
            if len(num.replace('-', '').replace('_', '').replace('.', '').replace('/', '')) < 3:
                continue

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0),
                "normalized": num,
                "context": context,
            })

        # 模式 3：编号[：:] + 编号内容（避免与合同编号重复）
        pattern3 = r'(?:^|[\n\r。，,;；])\s*编号\s*[:：]\s*([A-Za-z0-9\-_./]{4,})'
        for match in re.finditer(pattern3, text):
            num = match.group(1).strip()

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0),
                "normalized": num,
                "context": context,
            })

        return results

    def extract_clauses(self, text: str) -> list[dict]:
        """
        提取合同条款/章节标题

        检测模式：
        - 第一条 项目概况 / 第二条 工期
        - 第1条 合同标的 / 第2条 价款
        - 第一章 总则 / 第二章 合同主体

        Returns:
            [{"raw": "第一条 项目概况", "normalized": "项目概况", "clause_type": "条",
              "clause_num": "第一", "title": "项目概况", "context": "..."}, ...]
        """
        results = []

        # 匹配：第X条/节/章 + 后续标题文字
        pattern = r'(第[一二三四五六七八九十百千万\d]+[条章节])\s*([^\n\r,，。.;；]{1,50})'
        for match in re.finditer(pattern, text):
            clause_label = match.group(1)
            title = match.group(2).strip()

            # 推断类型
            if '章' in clause_label:
                clause_type = '章'
            elif '节' in clause_label:
                clause_type = '节'
            else:
                clause_type = '条'

            # 提取数字部分
            clause_num = clause_label.replace('第', '').replace(clause_type, '')

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": match.group(0),
                "normalized": title,
                "clause_type": clause_type,
                "clause_num": clause_num,
                "title": title,
                "context": context,
            })

        return results

    def extract_legal_terms(self, text: str) -> list[dict]:
        """
        提取关键法律条款关键词

        检测以下核心法律术语：
        - 违约责任
        - 争议解决 / 纠纷解决
        - 保密条款 / 保密义务
        - 知识产权
        - 不可抗力
        - 付款方式 / 支付方式 / 付款条件
        - 交付验收 / 验收标准

        Returns:
            [{"raw": "违约责任", "normalized": "违约责任", "category": "违约责任",
              "context": "..."}, ...]
        """
        results = []

        # 法律术语分类及其同义表达
        legal_term_map = {
            "违约责任": ["违约责任", "违约条款", "违约处理", "违约处罚"],
            "争议解决": ["争议解决", "纠纷解决", "争议处理", "争议管辖", "仲裁条款", "仲裁"],
            "保密条款": ["保密条款", "保密义务", "保密协议", "保密", "商业机密"],
            "知识产权": ["知识产权", "专利权", "商标权", "著作权", "版权"],
            "不可抗力": ["不可抗力", "免责条款", "免责事由"],
            "付款方式": ["付款方式", "支付方式", "付款条件", "付款时间", "付款期限", "付款安排"],
            "交付验收": ["交付验收", "验收标准", "验收条件", "验收程序", "验收方式", "交货验收"],
        }

        for category, patterns in legal_term_map.items():
            for p in patterns:
                for match in re.finditer(re.escape(p), text):
                    start = max(0, match.start() - 40)
                    end = min(len(text), match.end() + 40)
                    context = text[start:end].strip()

                    results.append({
                        "raw": match.group(0),
                        "normalized": category,
                        "category": category,
                        "context": context,
                    })

        # 去重（同一个category的同一个上下文start位置只保留一个，优先保留更长的raw）
        deduped = []
        seen = set()
        # 按 raw 长度降序排序，长的优先保留
        for r in sorted(results, key=lambda x: len(x["raw"]), reverse=True):
            key = (r["category"], r["context"][:20])
            if key not in seen:
                seen.add(key)
                deduped.append(r)

        return deduped

    def extract_contact_info(self, text: str) -> list[dict]:
        """
        提取联系方式（电话号码、邮箱）

        检测模式：
        - 手机号：1[3-9]XXXXXXXXX
        - 固定电话：XXX-XXXXXXXX / (XXX) XXXXXXXX
        - 邮箱：xxx@xxx.xxx

        Returns:
            [{"raw": "13800138000", "normalized": "13800138000", "type": "phone",
              "context": "..."}, ...]
        """
        results = []

        # 模式 1：手机号 — 11位，1开头，第二位3-9
        pattern1 = r'(?<!\d)(1[3-9]\d{9})(?!\d)'
        for match in re.finditer(pattern1, text):
            raw = match.group(0)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": raw,
                "normalized": raw,
                "type": "mobile",
                "context": context,
            })

        # 模式 2：固定电话 — 区号 + 号码
        # 格式：010-12345678 / 021-66668888 / (010) 12345678
        pattern2 = r'(?:\(\d{3,4}\)\s*)?(?<!\d)(\d{3,4}[- ]\d{7,8})(?!\d)'
        for match in re.finditer(pattern2, text):
            raw = match.group(1)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": raw,
                "normalized": raw.replace(' ', '-'),
                "type": "landline",
                "context": context,
            })

        # 模式 3：邮箱
        pattern3 = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        for match in re.finditer(pattern3, text):
            raw = match.group(0).strip()

            # 过滤明显不是邮箱的内容（如纯数字@数字）
            if re.match(r'\d+@\d+', raw):
                continue

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            results.append({
                "raw": raw,
                "normalized": raw.lower(),
                "type": "email",
                "context": context,
            })

        return results

    def extract_terms(self, text: str) -> list[dict]:
        """
        提取工期/期限/有效期信息

        检测模式：
        - 工期：120天 / 工期: 180日历天
        - 期限：3年 / 有效期至2025年12月31日
        - 合同有效期：自签订之日起3年
        - 服务期限：2024年1月1日至2025年12月31日

        Returns:
            [{"raw": "工期：120天", "normalized": "120天", "term_type": "工期",
              "context": "..."}, ...]
        """
        results = []

        # 工期/期限关键词及其规范化名称
        term_keywords = {
            "工期": ["工期", "施工工期", "合同工期"],
            "期限": ["期限", "合同期限", "服务期限", "有效期限", "履行期限"],
            "有效期": ["有效期", "合同有效期", "质保期", "质量保证期", "保修期"],
        }

        for term_type, keywords in term_keywords.items():
            for kw in keywords:
                # 模式：关键词[：:]，后跟内容到换行或句号
                pattern = re.escape(kw) + r'\s*[:：]?\s*([^\n\r。；;\.]{1,60})'
                for match in re.finditer(pattern, text):
                    raw_value = match.group(1).strip('.,;；;:： ')
                    # 过滤空内容
                    if not raw_value:
                        continue

                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 20)
                    context = text[start:end].strip()

                    results.append({
                        "raw": match.group(0),
                        "normalized": raw_value,
                        "term_type": term_type,
                        "context": context,
                    })

        return results

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def normalize_number(num_str: str) -> float:
        """将数字字符串标准化为浮点数"""
        return float(num_str.replace(',', ''))

    @staticmethod
    def normalize_date(date_str: str) -> str | None:
        """
        将日期字符串标准化为 YYYY-MM-DD 格式

        支持的格式：
        - 2024-01-15
        - 2024/01/15
        - 2024.01.15
        - 2024年1月15日
        - 2024年01月15号
        """
        # 统一分隔符
        normalized = date_str
        normalized = re.sub(r'[年/\.]', '-', normalized)
        normalized = normalized.replace('月', '-').replace('日', '').replace('号', '')
        normalized = normalized.strip('-')

        parts = normalized.split('-')
        if len(parts) != 3:
            return None

        try:
            year = parts[0]
            month = parts[1].zfill(2)
            day = parts[2].zfill(2)
            return f"{year}-{month}-{day}"
        except Exception:
            return None