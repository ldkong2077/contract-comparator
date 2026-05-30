"""
全文差异比对模块（兜底层）
使用 diff-match-patch 算法对 Word 和 PDF 全文进行逐字符比对
过滤格式噪音，输出结构化差异列表
"""
import re
from diff_match_patch import diff_match_patch


class FullTextDiff:
    """全文差异比对器"""

    def __init__(self):
        self.dmp = diff_match_patch()

    @staticmethod
    def normalize_for_diff(text: str) -> str:
        """
        文本预处理：过滤格式噪音，保留实质内容
        
        过滤项：
        - 连续空白字符 → 单空格
        - 纯空白行
        - 页眉页脚标记（可选）
        """
        # 统一换行符
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # 连续空白 → 单空格
        text = re.sub(r'[ \t]+', ' ', text)
        # 去除纯空白行
        lines = [line.strip() for line in text.split('\n')]
        lines = [line for line in lines if line]
        return '\n'.join(lines)

    def compare(self, word_text: str, pdf_text: str) -> dict:
        """
        执行全文差异比对
        
        Args:
            word_text: Word 文档全文
            pdf_text: PDF OCR 识别全文
            
        Returns:
            {
                "diffs": [
                    {
                        "type": "insert" | "delete" | "equal",
                        "text": "差异内容",
                        "context_before": "前文上下文",
                        "context_after": "后文上下文",
                        "risk_level": "high" | "medium" | "low",
                        "category": "text" | "number" | "date" | "keyword",
                    },
                    ...
                ],
                "summary": {
                    "total_changes": int,
                    "insertions": int,
                    "deletions": int,
                    "has_risk": bool,
                }
            }
        """
        # 预处理
        word_norm = self.normalize_for_diff(word_text)
        pdf_norm = self.normalize_for_diff(pdf_text)

        # 执行 diff
        diffs = self.dmp.diff_main(word_norm, pdf_norm)
        self.dmp.diff_cleanupSemantic(diffs)

        # 结构化输出
        structured_diffs = []
        full_text = ""
        
        # 先重建完整文本用于上下文提取
        for op, text in diffs:
            if op == 0:
                full_text += text
            elif op == -1:
                full_text += text
            elif op == 1:
                full_text += text

        # 提取差异项
        pos = 0
        for op, text in diffs:
            if op == 0:
                pos += len(text)
                continue

            # 提取上下文（前后各 50 字符）
            start = max(0, pos - 50)
            end = min(len(full_text), pos + len(text) + 50)
            context_before = full_text[start:pos]
            context_after = full_text[pos + len(text):end]

            # 判断风险等级和类别
            risk_level, category = self._classify_diff(text, op)

            structured_diffs.append({
                "type": "insert" if op == 1 else "delete",
                "text": text,
                "context_before": context_before,
                "context_after": context_after,
                "risk_level": risk_level,
                "category": category,
            })

            pos += len(text)

        # 统计摘要
        insertions = sum(1 for d in structured_diffs if d["type"] == "insert")
        deletions = sum(1 for d in structured_diffs if d["type"] == "delete")
        has_risk = any(d["risk_level"] == "high" for d in structured_diffs)

        return {
            "diffs": structured_diffs,
            "summary": {
                "total_changes": len(structured_diffs),
                "insertions": insertions,
                "deletions": deletions,
                "has_risk": has_risk,
            }
        }

    @staticmethod
    def _classify_diff(text: str, op: int) -> tuple:
        """
        分类差异项，判断风险等级和类别
        
        风险等级：
        - high: 涉及金额、数字、日期、关键法律术语的修改
        - medium: 涉及普通文字内容的修改
        - low: 标点、空格、格式类修改
        
        类别：
        - number: 数字相关
        - date: 日期相关
        - keyword: 关键法律术语
        - text: 普通文本
        """
        # 数字检测
        if re.search(r'\d+(?:,\d{3})*(?:\.\d+)?', text):
            return "high", "number"
        
        # 日期检测
        if re.search(r'\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}[日号]?', text):
            return "high", "date"
        
        # 关键法律术语检测
        legal_keywords = [
            '违约金', '赔偿金', '保证金', '押金', '罚金',
            '甲方', '乙方', '丙方',
            '解除', '终止', '无效', '撤销',
            '争议', '仲裁', '诉讼', '管辖',
            '保密', '知识产权', '违约责任',
            '不可抗力', '不可抗力事件',
            '生效', '履行', '交付', '验收',
        ]
        for kw in legal_keywords:
            if kw in text:
                return "high", "keyword"
        
        # 纯空白/标点 → low
        if re.match(r'^[\s\W_]+$', text, re.UNICODE):
            return "low", "text"
        
        # 默认 medium
        return "medium", "text"

    def generate_highlighted_html(self, word_text: str, pdf_text: str, max_diffs: int = 100) -> str:
        """
        生成带高亮的全文比对 HTML
        
        Args:
            word_text: Word 原文
            pdf_text: PDF 文本
            max_diffs: 最大显示差异数（避免过长）
            
        Returns:
            HTML 字符串
        """
        result = self.compare(word_text, pdf_text)
        diffs = result["diffs"][:max_diffs]

        html_parts = ['<div class="full-text-diff">']
        
        for diff in diffs:
            risk_class = f"diff-{diff['risk_level']}"
            type_label = "新增" if diff["type"] == "insert" else "删除"
            type_class = "diff-insert" if diff["type"] == "insert" else "diff-delete"
            
            html_parts.append(f"""
            <div class="diff-item {risk_class}">
                <div class="diff-header">
                    <span class="diff-type {type_class}">{type_label}</span>
                    <span class="diff-category">{diff['category']}</span>
                    <span class="diff-risk">{diff['risk_level'].upper()}</span>
                </div>
                <div class="diff-content">{self._escape_html(diff['text'])}</div>
                <div class="diff-context">
                    <span class="context-before">...{self._escape_html(diff['context_before'][-30:])}</span>
                    <span class="context-after">{self._escape_html(diff['context_after'][:30])}...</span>
                </div>
            </div>
            """)

        html_parts.append('</div>')
        return '\n'.join(html_parts)

    @staticmethod
    def _escape_html(text: str) -> str:
        """转义 HTML 特殊字符"""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
