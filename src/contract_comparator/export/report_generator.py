"""
报告生成模块
生成比对结果报告（文本/JSON/HTML 格式）
"""
import os
import json
from datetime import datetime


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def generate_text_report(
        self,
        word_path: str,
        pdf_path: str,
        comparison_result: dict,
        summary: dict,
        low_confidence_items: list | None = None,
    ) -> str:
        """
        生成文本格式报告
        
        Returns:
            报告文件路径
        """
        lines = []
        lines.append("=" * 60)
        lines.append("合同扫描件比对报告")
        lines.append("=" * 60)
        lines.append(f"比对时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Word 文档: {os.path.basename(word_path)}")
        lines.append(f"扫描 PDF: {os.path.basename(pdf_path)}")
        lines.append("")
        
        # 摘要
        lines.append("--- 比对摘要 ---")
        if summary["total_diffs"] == 0:
            lines.append("[OK] 所有关键字段一致，未发现差异")
        else:
            lines.append(f"[WARN] 发现 {summary['total_diffs']} 处差异")
            if summary["has_critical_diff"]:
                lines.append("[!!] 存在金额相关差异，请重点核查！")
        lines.append("")
        
        # 数字比对结果
        lines.append("--- 数字比对 ---")
        nums = comparison_result["numbers"]
        if not nums["has_diff"]:
            lines.append(f"[OK] 所有数字一致（共 {len(nums['matched'])} 个）")
        else:
            if nums["missing_in_pdf"]:
                lines.append("[DIFF] 扫描件缺失数字:")
                for item in nums["missing_in_pdf"]:
                    lines.append(f"   * {item['raw']} (上下文: ...{item['context']}...)")
            if nums["extra_in_pdf"]:
                lines.append("[DIFF] 扫描件多出数字:")
                for item in nums["extra_in_pdf"]:
                    lines.append(f"   * {item['raw']} (上下文: ...{item['context']}...)")
        lines.append("")
        
        # 日期比对结果
        lines.append("--- 日期比对 ---")
        dates = comparison_result["dates"]
        if not dates["has_diff"]:
            lines.append(f"[OK] 所有日期一致（共 {len(dates['matched'])} 个）")
        else:
            if dates["missing_in_pdf"]:
                lines.append("[DIFF] 扫描件缺失日期:")
                for item in dates["missing_in_pdf"]:
                    lines.append(f"   * Word: {item['raw']} -> 标准化: {item['normalized']}")
            if dates["extra_in_pdf"]:
                lines.append("[DIFF] 扫描件多出日期:")
                for item in dates["extra_in_pdf"]:
                    lines.append(f"   * PDF: {item['raw']} -> 标准化: {item['normalized']}")
        lines.append("")
        
        # 大写金额比对
        lines.append("--- 大写金额比对 ---")
        amounts_w = comparison_result["amounts_words"]
        if not amounts_w["has_diff"]:
            lines.append(f"[OK] 所有大写金额一致（共 {len(amounts_w['matched'])} 个）")
        else:
            if amounts_w["missing_in_pdf"]:
                lines.append("[DIFF] 扫描件缺失大写金额:")
                for item in amounts_w["missing_in_pdf"]:
                    lines.append(f"   * Word: {item['raw']}")
            if amounts_w["extra_in_pdf"]:
                lines.append("[DIFF] 扫描件多出大写金额:")
                for item in amounts_w["extra_in_pdf"]:
                    lines.append(f"   * PDF: {item['raw']}")
        lines.append("")
        
        # 金额数字比对
        lines.append("--- 金额数字比对 ---")
        amounts_d = comparison_result["amounts_digits"]
        if not amounts_d["has_diff"]:
            lines.append(f"[OK] 所有金额数字一致（共 {len(amounts_d['matched'])} 对）")
        else:
            if amounts_d["missing_in_pdf"]:
                lines.append("[DIFF] 扫描件缺失金额:")
                for item in amounts_d["missing_in_pdf"]:
                    lines.append(f"   * Word: {item['keyword']} = {item['raw']}")
            if amounts_d["extra_in_pdf"]:
                lines.append("[DIFF] 扫描件多出金额:")
                for item in amounts_d["extra_in_pdf"]:
                    lines.append(f"   * PDF: {item['keyword']} = {item['raw']}")
        lines.append("")
        
        # 百分比比对
        lines.append("--- 百分比比对 ---")
        pcts = comparison_result["percentages"]
        if not pcts["has_diff"]:
            lines.append(f"[OK] 所有百分比一致（共 {len(pcts['matched'])} 个）")
        else:
            if pcts["missing_in_pdf"]:
                lines.append("[DIFF] 扫描件缺失百分比:")
                for item in pcts["missing_in_pdf"]:
                    lines.append(f"   * Word: {item['raw']}")
            if pcts["extra_in_pdf"]:
                lines.append("[DIFF] 扫描件多出百分比:")
                for item in pcts["extra_in_pdf"]:
                    lines.append(f"   * PDF: {item['raw']}")
        lines.append("")
        
        # 低置信度项目
        if low_confidence_items:
            lines.append("--- 低置信度字段（需人工复核）---")
            for item in low_confidence_items:
                lines.append(
                    f"   • \"{item['text']}\" (置信度: {item['confidence']:.2f}, "
                    f"页码: {item.get('page', '?')})"
                )
            lines.append("")
        
        # 总结
        lines.append("=" * 60)
        lines.append(f"总结: 发现 {summary['total_diffs']} 处差异")
        if summary["has_critical_diff"]:
            lines.append("建议: 金额相关差异需重点人工核查")
        if low_confidence_items:
            lines.append(f"另有 {len(low_confidence_items)} 处低置信度字段需复核")
        lines.append("=" * 60)
        
        # 写入文件
        report_path = os.path.join(self.output_dir, "comparison_report.txt")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        
        return report_path
    
    def generate_json_report(
        self,
        word_path: str,
        pdf_path: str,
        comparison_result: dict,
        summary: dict,
        low_confidence_items: list | None = None,
    ) -> str:
        """生成 JSON 格式报告"""
        report = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "word_file": word_path,
                "pdf_file": pdf_path,
            },
            "summary": summary,
            "details": comparison_result,
            "low_confidence_items": low_confidence_items or [],
        }
        
        report_path = os.path.join(self.output_dir, "comparison_report.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return report_path
