"""
合同比对工具 - 商用级专业界面 (v4.0)
"""
import os
import sys
import tempfile
import time
import re
import base64
import json
from datetime import datetime
from typing import Optional

import streamlit as st

from contract_comparator.engine.pdf_processor import pdf_to_images
from contract_comparator.engine.ocr.engine import OCREngine
from contract_comparator.engine.word_parser import WordParser
from contract_comparator.compare.field_extractor import FieldExtractor
from contract_comparator.compare.comparator import Comparator
from contract_comparator.compare.full_text_diff import FullTextDiff
from contract_comparator.llm.llm_engine import LLMEngine

# --- 可选模块导入（优雅降级） ---
try:
    from contract_comparator.export.report_exporter import (
        export_redline_docx,
        export_diff_excel,
        export_pdf_report,
        export_json_api,
        export_full_package,
    )
    _REPORT_EXPORTER_AVAILABLE = True
except ImportError:
    _REPORT_EXPORTER_AVAILABLE = False

try:
    from contract_comparator.security import SensitiveDataMasker
    _SECURITY_AVAILABLE = True
except ImportError:
    _SECURITY_AVAILABLE = False

try:
    from contract_comparator.compare.excel_comparator import ExcelComparator, generate_diff_excel as generate_excel_diff_report
    _EXCEL_COMPARATOR_AVAILABLE = True
except ImportError:
    _EXCEL_COMPARATOR_AVAILABLE = False

try:
    from contract_comparator.database import DatabaseManager, get_database
    _DATABASE_AVAILABLE = True
except ImportError:
    _DATABASE_AVAILABLE = False

_PROFILES_AVAILABLE = False  # profiles.py 当前为空模块，暂不启用

# 支持的图片文件扩展名
_IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "bmp", "tiff", "webp"]

# 行业预设对应的字段类别
_INDUSTRY_FIELDS = {
    "通用": ["金额数字", "大写金额", "日期", "百分比", "数字", "当事方", "合同编号", "法律条款", "联系方式", "期限"],
    "租赁": ["租金", "押金", "租期", "面积", "物业费", "违约金", "付款方式", "交付验收"],
    "采购": ["单价", "总价", "数量", "交货期", "验收标准", "质保期", "付款条件", "违约责任"],
    "劳动": ["工资", "社保", "试用期", "合同期限", "工作地点", "岗位", "保密义务", "竞业限制"],
    "工程": ["工程造价", "工期", "质量标准", "验收标准", "违约金", "保证金", "付款方式", "变更条款"],
}

st.set_page_config(
    page_title="合同比对专业版",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Session State 初始化
# ============================================================

def init_session_state() -> None:
    """初始化 session state"""
    defaults = {
        # 核心比对数据
        "word_text": "",
        "pdf_text": "",
        "comparison_result": None,
        "summary": None,
        "word_fields": None,
        "pdf_fields": None,
        "word_paragraphs": [],
        "running": False,
        "highlighted_word_html": "",
        "pdf_display_text": "",
        "diff_list": [],
        "selected_diff_idx": -1,
        "full_text_diff_result": None,
        "llm_analysis_result": None,
        "low_confidence": None,
        # OCR / PDF 图片
        "pdf_image_paths": [],
        "ocr_results": None,
        # 比对历史（会话内）
        "comparison_history": [],
        "active_history_idx": -1,
        # 设置
        "ocr_confidence_threshold": 0.5,
        "enable_llm": False,
        "enable_full_text_diff": True,
        "enable_sensitive_masking": False,
        "comparison_tolerance": 0.01,
        # LLM Provider 选择
        "llm_provider": "ollama",
        "claude_api_key": "",
        # 差异过滤状态
        "diff_filter_risk": "全部",
        "diff_filter_type": "全部",
        # 导出
        "last_export_data": None,
        # 运行时间统计
        "timing_stats": {},
        # PDF 视图模式
        "pdf_view_mode": "叠加视图",
        # Excel 对比结果
        "excel_comparison_result": None,
        # 错误状态
        "last_error": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ============================================================
# 核心比对流程（使用 st.status 渐进式加载）
# ============================================================

def run_comparison(word_file: str, pdf_file: str, output_dir: str) -> bool:
    """执行完整的比对流程，使用 st.status 渐进显示进度"""
    timing = {}
    try:
        with st.status("正在执行合同比对...", expanded=True) as status:
            # ---------- Step 1: Word 解析 ----------
            t0 = time.time()
            st.write("📝 正在解析 Word 文档...")
            try:
                word_parser = WordParser(str(word_file))
                word_result = word_parser.parse()
                word_text = word_result["full_text"]
                word_paragraphs = word_result.get("paragraphs", [])
                st.session_state.word_paragraphs = word_paragraphs
            except Exception as e:
                raise RuntimeError(f"Word 文档解析失败：{e}，请确认文件为有效的 .docx 格式")
            timing["word_parse"] = round(time.time() - t0, 2)
            st.write(
                f"✅ Word 解析完成：{word_result['paragraph_count']} 个段落，"
                f"{word_result['table_count']} 个表格 ({timing['word_parse']}s)"
            )

            # ---------- Step 2: PDF 转图片 / 图片直接 OCR ----------
            t0 = time.time()
            ocr_engine = OCREngine()

            # 判断是否为图片文件（直接 OCR，无需 PDF 转换）
            pdf_ext = os.path.splitext(str(pdf_file))[1].lower()
            is_image_file = pdf_ext.lstrip('.') in _IMAGE_EXTENSIONS

            if is_image_file:
                # 图片文件直接 OCR
                st.write("🖼️ 正在识别图片文件...")
                try:
                    ocr_results = ocr_engine.recognize_image(str(pdf_file))
                    pdf_text = ocr_engine.get_full_text(ocr_results)
                    low_confidence = ocr_engine.get_low_confidence_items(ocr_results)
                    image_paths = [str(pdf_file)]
                except Exception as e:
                    raise RuntimeError(f"图片 OCR 识别失败：{e}，请确认图片清晰且格式正确")
                st.session_state.pdf_image_paths = image_paths
                st.session_state.ocr_results = ocr_results
                timing["ocr"] = round(time.time() - t0, 2)
                st.write(f"✅ 图片 OCR 识别完成：{len(ocr_results)} 个文本块 ({timing['ocr']}s)")
            else:
                # PDF 文件：先转图片再 OCR
                st.write("🖼️ 正在转换 PDF 为图片...")
                try:
                    image_dir = os.path.join(output_dir, "images")
                    os.makedirs(image_dir, exist_ok=True)
                    image_paths = pdf_to_images(str(pdf_file), output_dir=image_dir)
                    st.session_state.pdf_image_paths = image_paths
                except Exception as e:
                    raise RuntimeError(f"PDF 转图片失败：{e}，请确认文件为有效的 PDF 格式且未加密")
                timing["pdf_convert"] = round(time.time() - t0, 2)
                st.write(f"✅ PDF 转换完成：{len(image_paths)} 页 ({timing['pdf_convert']}s)")

                # ---------- Step 3: OCR ----------
                t0 = time.time()
                st.write("🔍 正在进行 OCR 识别...")
                try:
                    ocr_results = ocr_engine.recognize_pdf(image_paths)
                    pdf_text = ocr_engine.get_full_text(ocr_results)
                    low_confidence = ocr_engine.get_low_confidence_items(ocr_results)
                    st.session_state.ocr_results = ocr_results
                except Exception as e:
                    raise RuntimeError(f"OCR 识别失败：{e}，请确认扫描件清晰可读")
                timing["ocr"] = round(time.time() - t0, 2)
                st.write(f"✅ OCR 识别完成：{len(ocr_results)} 个文本块 ({timing['ocr']}s)")

            # ---------- Step 4: 字段抽取 ----------
            t0 = time.time()
            st.write("🏷️ 正在抽取关键字段...")
            try:
                extractor = FieldExtractor()
                word_fields = extractor.extract_all(word_text, source="word")
                pdf_fields = extractor.extract_all(pdf_text, source="pdf")
            except Exception as e:
                raise RuntimeError(f"字段抽取失败：{e}")
            timing["extraction"] = round(time.time() - t0, 2)
            st.write(f"✅ 字段抽取完成 ({timing['extraction']}s)")

            # ---------- Step 5: 比对 ----------
            t0 = time.time()
            st.write("⚖️ 正在执行比对...")
            try:
                comparator = Comparator()
                comparison_result = comparator.compare(word_fields, pdf_fields)
                summary = comparator.get_summary(comparison_result)
            except Exception as e:
                raise RuntimeError(f"比对执行失败：{e}")
            timing["comparison"] = round(time.time() - t0, 2)
            st.write(
                f"✅ 比对完成：发现 {summary['total_diffs']} 处差异 ({timing['comparison']}s)"
            )

            highlighted_html = generate_highlighted_word_html(word_text, comparison_result)
            pdf_display = format_pdf_display_text(pdf_text)
            diff_list = build_diff_list(comparison_result)

            # ---------- Step 6: 全文 diff 兜底 ----------
            full_text_diff_result = None
            if st.session_state.enable_full_text_diff:
                t0 = time.time()
                st.write("📊 正在执行全文差异比对...")
                try:
                    full_text_differ = FullTextDiff()
                    full_text_diff_result = full_text_differ.compare(word_text, pdf_text)
                    timing["full_text_diff"] = round(time.time() - t0, 2)
                    st.write(
                        f"✅ 全文比对完成：发现 "
                        f"{full_text_diff_result['summary']['total_changes']} 处变更 "
                        f"({timing['full_text_diff']}s)"
                    )
                except Exception as e:
                    st.warning(f"⚠️ 全文差异比对失败：{e}，已跳过")
            else:
                st.write("⏭️ 全文差异比对已跳过（设置中已关闭）")

            # ---------- Step 7: LLM 语义分析 ----------
            llm_analysis_result = None
            if st.session_state.enable_llm:
                t0 = time.time()
                st.write("🤖 正在启动 AI 语义分析...")
                try:
                    # 根据用户选择创建 LLM 引擎
                    provider_name = st.session_state.llm_provider
                    llm_kwargs = {}
                    if provider_name == "claude":
                        api_key = st.session_state.get("claude_api_key", "")
                        if not api_key:
                            raise RuntimeError("Claude API Key 未设置，请在侧边栏设置中输入")
                        llm_kwargs["api_key"] = api_key
                    llm_engine = LLMEngine(provider=provider_name, **llm_kwargs)
                    llm_analysis_result = llm_engine.analyze_semantic_diff(
                        word_text, pdf_text, field_diffs=diff_list
                    )
                    timing["llm"] = round(time.time() - t0, 2)
                    if llm_engine.is_available():
                        st.write(f"✅ AI 语义分析完成 ({timing['llm']}s)")
                    else:
                        st.warning("LLM 服务未启用，跳过语义分析（可在侧边栏设置中配置 Provider）")
                except RuntimeError as e:
                    st.warning(f"⚠️ {e}")
                except Exception as e:
                    st.warning(f"⚠️ AI 语义分析失败：{e}，已跳过")
            else:
                st.write("⏭️ AI 语义分析已跳过（设置中已关闭）")

            # ---------- 保存到 session ----------
            st.session_state.word_text = word_text
            st.session_state.pdf_text = pdf_text
            st.session_state.comparison_result = comparison_result
            st.session_state.summary = summary
            st.session_state.word_fields = word_fields
            st.session_state.pdf_fields = pdf_fields
            st.session_state.low_confidence = low_confidence
            st.session_state.highlighted_word_html = highlighted_html
            st.session_state.pdf_display_text = pdf_display
            st.session_state.diff_list = diff_list
            st.session_state.selected_diff_idx = -1
            st.session_state.full_text_diff_result = full_text_diff_result
            st.session_state.llm_analysis_result = llm_analysis_result
            st.session_state.timing_stats = timing
            st.session_state.last_error = None

            status.update(label="✅ 比对完成！", state="complete")

        # ---------- 添加到历史 ----------
        _add_to_history(word_file, pdf_file, summary)

        return True

    except RuntimeError as e:
        st.error(f"❌ {e}")
        st.session_state.last_error = str(e)
        return False
    except MemoryError:
        st.error("❌ 文件过大导致内存不足，请尝试上传更小的文件（建议 < 50MB）")
        st.session_state.last_error = "文件过大导致内存不足"
        return False
    except Exception as e:
        error_msg = str(e)
        # 友好化常见错误
        if "No such file" in error_msg or "FileNotFoundError" in error_msg:
            friendly = "文件读取失败，请确认文件存在且未被移动"
        elif "Permission denied" in error_msg:
            friendly = "文件权限不足，请确认文件未被其他程序占用"
        elif "is not a valid" in error_msg.lower() or "corrupted" in error_msg.lower():
            friendly = "文件格式无效或已损坏，请确认文件格式正确"
        else:
            friendly = f"比对过程出错：{error_msg}"
        st.error(f"❌ {friendly}")
        st.session_state.last_error = friendly
        import traceback
        with st.expander("查看详细错误信息"):
            st.code(traceback.format_exc())
        return False


# ============================================================
# 比对历史（会话内）
# ============================================================

def _add_to_history(word_file: str, pdf_file: str, summary: dict) -> None:
    """将当前比对添加到会话历史"""
    entry = {
        "id": len(st.session_state.comparison_history),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "word_name": os.path.basename(str(word_file)) if word_file else "未知",
        "pdf_name": os.path.basename(str(pdf_file)) if pdf_file else "未知",
        "total_diffs": summary.get("total_diffs", 0),
        "has_critical": summary.get("has_critical_diff", False),
        # 快照当前结果索引
        "snapshot": {
            "summary": summary,
            "comparison_result": st.session_state.comparison_result,
            "diff_list": st.session_state.diff_list,
            "highlighted_word_html": st.session_state.highlighted_word_html,
            "pdf_display_text": st.session_state.pdf_display_text,
            "full_text_diff_result": st.session_state.full_text_diff_result,
            "llm_analysis_result": st.session_state.llm_analysis_result,
            "timing_stats": st.session_state.timing_stats,
        },
    }
    st.session_state.comparison_history.append(entry)
    st.session_state.active_history_idx = entry["id"]


def _restore_from_history(idx: int) -> None:
    """从历史记录恢复比对结果"""
    entry = st.session_state.comparison_history[idx]
    snap = entry["snapshot"]
    st.session_state.summary = snap["summary"]
    st.session_state.comparison_result = snap["comparison_result"]
    st.session_state.diff_list = snap["diff_list"]
    st.session_state.highlighted_word_html = snap["highlighted_word_html"]
    st.session_state.pdf_display_text = snap["pdf_display_text"]
    st.session_state.full_text_diff_result = snap["full_text_diff_result"]
    st.session_state.llm_analysis_result = snap["llm_analysis_result"]
    st.session_state.timing_stats = snap["timing_stats"]
    st.session_state.active_history_idx = idx
    st.session_state.selected_diff_idx = -1


# ============================================================
# HTML 工具函数
# ============================================================

def escape_html(text: str) -> str:
    """转义 HTML 特殊字符（完整版，防止 XSS）"""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("/", "&#47;")
    )


# ============================================================
# 差异列表构建
# ============================================================

def build_diff_list(comparison_result: dict) -> list[dict]:
    """构建差异导航列表（含 missing_in_pdf 和 extra_in_pdf）"""
    diffs = []

    def _add_diffs(items, diff_type, risk, is_extra=False):
        prefix = "[多出]" if is_extra else ""
        for item in items:
            diffs.append({
                "type": f"{prefix}{diff_type}",
                "risk": risk,
                "text": item["raw"],
                "keyword": item.get("keyword", ""),
                "phrase": item.get("phrase", item.get("context", "")),
            })

    # 金额数字差异
    _add_diffs(comparison_result["amounts_digits"].get("missing_in_pdf", []), "金额数字", "high")
    _add_diffs(comparison_result["amounts_digits"].get("extra_in_pdf", []), "金额数字", "high", is_extra=True)
    # 大写金额差异
    _add_diffs(comparison_result["amounts_words"].get("missing_in_pdf", []), "大写金额", "high")
    _add_diffs(comparison_result["amounts_words"].get("extra_in_pdf", []), "大写金额", "high", is_extra=True)
    # 数字差异
    _add_diffs(comparison_result["numbers"].get("missing_in_pdf", []), "数字", "medium")
    _add_diffs(comparison_result["numbers"].get("extra_in_pdf", []), "数字", "medium", is_extra=True)
    # 日期差异
    _add_diffs(comparison_result["dates"].get("missing_in_pdf", []), "日期", "medium")
    _add_diffs(comparison_result["dates"].get("extra_in_pdf", []), "日期", "medium", is_extra=True)
    # 百分比差异
    _add_diffs(comparison_result["percentages"].get("missing_in_pdf", []), "百分比", "low")
    _add_diffs(comparison_result["percentages"].get("extra_in_pdf", []), "百分比", "low", is_extra=True)

    return diffs


# ============================================================
# 高亮 / 显示格式化
# ============================================================

def generate_highlighted_word_html(word_text: str, comparison_result: dict | None) -> str:
    """在 Word 原文中高亮显示差异部分"""
    if not comparison_result:
        return escape_html(word_text)

    highlights = []
    for item in comparison_result["amounts_digits"].get("missing_in_pdf", []):
        highlights.append((item["raw"], "hl-amount"))
    for item in comparison_result["amounts_words"].get("missing_in_pdf", []):
        highlights.append((item["raw"], "hl-amount"))
    for item in comparison_result["numbers"].get("missing_in_pdf", []):
        highlights.append((item["raw"], "hl-number"))
    for item in comparison_result["dates"].get("missing_in_pdf", []):
        highlights.append((item["raw"], "hl-date"))
    for item in comparison_result["percentages"].get("missing_in_pdf", []):
        highlights.append((item["raw"], "hl-percent"))

    highlights.sort(key=lambda x: len(x[0]), reverse=True)

    paragraphs = word_text.split("\n")
    html_parts = []

    for para in paragraphs:
        escaped = escape_html(para)
        for text, hl_type in highlights:
            escaped_text = escape_html(text)
            if escaped_text in escaped:
                escaped = escaped.replace(escaped_text, f'<span class="{hl_type}">{escaped_text}</span>', 1)
        html_parts.append(escaped)

    return "\n".join(html_parts)


def format_pdf_display_text(pdf_text: str) -> str:
    """格式化 PDF OCR 文本用于显示"""
    paragraphs = pdf_text.split("\n")
    html_parts = []
    for para in paragraphs:
        escaped = escape_html(para)
        if escaped.strip():
            html_parts.append(escaped)
        else:
            html_parts.append("<br>")
    return "\n".join(html_parts)


# ============================================================
# 同步滚动组件
# ============================================================

def render_sync_scroll_component(word_html: str, pdf_html: str) -> None:
    """渲染带同步滚动的双文档视图"""
    sync_js = """
export default function(component) {
    const { data, parentElement } = component;
    if (!data || !data.word || !data.pdf) return;

    parentElement.innerHTML = '';

    const container = document.createElement('div');
    container.className = 'sync-scroll-container';

    const leftPanel = document.createElement('div');
    leftPanel.className = 'doc-panel';
    leftPanel.innerHTML = data.word;

    const rightPanel = document.createElement('div');
    rightPanel.className = 'doc-panel';
    rightPanel.innerHTML = data.pdf;

    container.appendChild(leftPanel);
    container.appendChild(rightPanel);
    parentElement.appendChild(container);

    let syncing = false;
    const panels = [leftPanel, rightPanel];

    panels.forEach(panel => {
        panel.addEventListener('scroll', (e) => {
            if (syncing) return;
            syncing = true;
            const source = e.target;
            const scrollRatio = source.scrollTop / (source.scrollHeight - source.clientHeight || 1);
            panels.forEach(target => {
                if (target !== source) {
                    target.scrollTop = scrollRatio * (target.scrollHeight - target.clientHeight);
                }
            });
            requestAnimationFrame(() => { syncing = false; });
        });
    });
}
"""

    sync_css = """
.sync-scroll-container {
    display: flex;
    gap: 0;
    height: 70vh;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
    background: #fafafa;
}
.doc-panel {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 16px 20px;
    font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif;
    font-size: 14px;
    line-height: 1.85;
    white-space: pre-wrap;
    word-wrap: break-word;
    background: #ffffff;
}
.doc-panel:first-child {
    border-right: 2px solid #e0e0e0;
}
.doc-panel::-webkit-scrollbar {
    width: 8px;
}
.doc-panel::-webkit-scrollbar-track {
    background: #f1f1f1;
}
.doc-panel::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
}
.doc-panel::-webkit-scrollbar-thumb:hover {
    background: #a1a1a1;
}

.hl-amount {
    background-color: #ffcdd2;
    padding: 1px 5px;
    border-radius: 3px;
    border-bottom: 2px solid #d32f2f;
    font-weight: 700;
    color: #b71c1c;
}
.hl-number {
    background-color: #ffe0b2;
    padding: 1px 5px;
    border-radius: 3px;
    border-bottom: 2px solid #f57c00;
    font-weight: 700;
    color: #e65100;
}
.hl-date {
    background-color: #fff9c4;
    padding: 1px 5px;
    border-radius: 3px;
    border-bottom: 2px solid #fbc02d;
    font-weight: 700;
    color: #f57f17;
}
.hl-percent {
    background-color: #e1bee7;
    padding: 1px 5px;
    border-radius: 3px;
    border-bottom: 2px solid #8e24aa;
    font-weight: 700;
    color: #6a1b9a;
}
"""

    st.components.v2.component(  # type: ignore
        "sync_scroll_v2",
        css=sync_css,
        js=sync_js,
    )(data={"word": word_html, "pdf": pdf_html}, height=700)


# ============================================================
# 导出报表
# ============================================================

def generate_export_report() -> str:
    """生成可导出的 HTML 报告"""
    summary = st.session_state.summary
    comparison_result = st.session_state.comparison_result
    word_html = st.session_state.highlighted_word_html
    pdf_text = st.session_state.pdf_display_text

    report = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>合同比对报告</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 40px; color: #333; }}
h1 {{ color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 10px; }}
.summary {{ background: #f8f9fb; padding: 20px; border-radius: 8px; margin: 20px 0; }}
.diff-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
.diff-table th, .diff-table td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
.diff-table th {{ background: #1a1a2e; color: #fff; }}
.diff-table tr:nth-child(even) {{ background: #f8f9fb; }}
.hl-amount {{ background: #ffcdd2; padding: 1px 4px; border-bottom: 2px solid #d32f2f; font-weight: bold; }}
.hl-number {{ background: #ffe0b2; padding: 1px 4px; border-bottom: 2px solid #f57c00; font-weight: bold; }}
.hl-date {{ background: #fff9c4; padding: 1px 4px; border-bottom: 2px solid #fbc02d; font-weight: bold; }}
.doc-view {{ max-height: 600px; overflow-y: auto; border: 1px solid #ddd; padding: 16px; background: #fff; margin: 10px 0; }}
</style>
</head>
<body>
<h1>合同比对报告</h1>
<div class="summary">
<p><b>差异总数:</b> {summary["total_diffs"]}</p>
<p><b>存在金额差异:</b> {"是" if summary["has_critical_diff"] else "否"}</p>
<p><b>差异类型:</b> {"、".join(d["type"] for d in summary["diff_details"])}</p>
</div>

<h2>差异明细</h2>
<table class="diff-table">
<tr><th>类型</th><th>Word 原文</th><th>PDF 扫描件</th><th>状态</th></tr>
"""

    for item in comparison_result["amounts_digits"].get("missing_in_pdf", []):
        report += f'<tr><td>金额数字</td><td>{escape_html(item["raw"])}</td><td>缺失</td><td style="color:red;">差异</td></tr>\n'
    for item in comparison_result["dates"].get("missing_in_pdf", []):
        report += f'<tr><td>日期</td><td>{escape_html(item["raw"])}</td><td>缺失</td><td style="color:orange;">差异</td></tr>\n'
    for item in comparison_result["numbers"].get("missing_in_pdf", []):
        report += f'<tr><td>数字</td><td>{escape_html(item["raw"])}</td><td>缺失</td><td style="color:orange;">差异</td></tr>\n'

    report += f"""
</table>

<h2>原文档（高亮显示差异）</h2>
<div class="doc-view">{word_html}</div>

<h2>扫描件 OCR 文本</h2>
<div class="doc-view">{pdf_text}</div>

<p style="margin-top: 40px; color: #999; font-size: 0.8rem;">报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</body>
</html>"""
    return report


def _make_download_button(label: str, data: bytes, file_name: str, mime: str) -> None:
    """通用下载按钮"""
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:{mime};base64,{b64}" download="{file_name}" class="download-link">{label}</a>'
    st.markdown(href, unsafe_allow_html=True)


def render_export_buttons() -> None:
    """渲染多格式导出按钮"""
    if not _REPORT_EXPORTER_AVAILABLE:
        # 降级：仅基础的 HTML 导出
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 导出 HTML 报告", use_container_width=True, key="export_html"):
                report_html = generate_export_report()
                st.download_button(
                    label="点击下载报告",
                    data=report_html,
                    file_name="合同比对报告.html",
                    mime="text/html",
                    use_container_width=True,
                )
        return

    cr = st.session_state.comparison_result
    sm = st.session_state.summary
    wt = st.session_state.word_text
    pt = st.session_state.pdf_text
    dl = st.session_state.diff_list

    st.markdown("### 📦 导出报表")
    col1, col2, col3, col4, col5 = st.columns(5)

    # Word 红线
    with col1:
        try:
            docx_data = export_redline_docx(cr, sm, wt, pt, dl)
            st.download_button(
                label="📝 Word红线",
                data=docx_data,
                file_name="合同比对报告_修订版.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
                key="dl_docx",
            )
        except Exception as e:
            st.button("📝 Word红线", disabled=True, use_container_width=True, key="dl_docx_err")
            st.caption(f"导出失败: {e}")

    # Excel
    with col2:
        try:
            xlsx_data = export_diff_excel(cr, sm, wt, pt, dl)
            st.download_button(
                label="📊 Excel明细",
                data=xlsx_data,
                file_name="合同比对报告_差异明细.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dl_xlsx",
            )
        except Exception as e:
            st.button("📊 Excel明细", disabled=True, use_container_width=True, key="dl_xlsx_err")
            st.caption(f"导出失败: {e}")

    # PDF
    with col3:
        try:
            pdf_data = export_pdf_report(cr, sm, wt, pt, dl)
            st.download_button(
                label="📄 PDF报告",
                data=pdf_data,
                file_name="合同比对报告.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dl_pdf",
            )
        except Exception as e:
            st.button("📄 PDF报告", disabled=True, use_container_width=True, key="dl_pdf_err")
            st.caption(f"导出失败: {e}")

    # JSON
    with col4:
        try:
            json_str = export_json_api(cr, sm, wt, pt, dl)
            st.download_button(
                label="🔧 JSON数据",
                data=json_str,
                file_name="合同比对报告.json",
                mime="application/json",
                use_container_width=True,
                key="dl_json",
            )
        except Exception as e:
            st.button("🔧 JSON数据", disabled=True, use_container_width=True, key="dl_json_err")
            st.caption(f"导出失败: {e}")

    # ZIP
    with col5:
        try:
            zip_data = export_full_package(cr, sm, wt, pt, dl)
            st.download_button(
                label="📦 完整包(.zip)",
                data=zip_data,
                file_name="合同比对报告_完整包.zip",
                mime="application/zip",
                use_container_width=True,
                key="dl_zip",
            )
        except Exception as e:
            st.button("📦 完整包(.zip)", disabled=True, use_container_width=True, key="dl_zip_err")
            st.caption(f"导出失败: {e}")


# ============================================================
# 敏感数据脱敏包装
# ============================================================

def _apply_sensitive_masking(text: str) -> str:
    """如果启用了脱敏，则对文本敏感数据做遮盖"""
    if not st.session_state.enable_sensitive_masking:
        return text
    if not _SECURITY_AVAILABLE:
        return text
    try:
        masked, _items = SensitiveDataMasker.mask_all(text)
        return masked
    except Exception:
        return text


# ============================================================
# PDF 图片 + OCR 覆盖视图
# ============================================================

def render_pdf_image_ocr_tab() -> None:
    """渲染 PDF 原始图片 + OCR 文本叠加视图"""
    image_paths = st.session_state.get("pdf_image_paths", [])
    ocr_results = st.session_state.get("ocr_results")
    low_confidence = st.session_state.get("low_confidence")
    threshold = st.session_state.ocr_confidence_threshold

    if not image_paths:
        st.info("未找到 PDF 页面图像。请先完成一次比对。")
        return

    view_mode = st.radio(
        "查看模式",
        ["仅原图", "仅OCR文本", "叠加视图"],
        horizontal=True,
        key="pdf_view_mode_radio",
    )

    st.session_state.pdf_view_mode = view_mode

    if view_mode == "仅原图":
        page_idx = st.slider("选择页码", 1, len(image_paths), 1, key="pdf_img_page") - 1
        img_path = image_paths[page_idx]
        with open(img_path, "rb") as f:
            st.image(f.read(), caption=f"第 {page_idx + 1} 页 / 共 {len(image_paths)} 页",
                     use_container_width=True)

    elif view_mode == "仅OCR文本":
        if ocr_results:
            page_idx = st.slider("选择页码", 1, len(ocr_results), 1, key="pdf_ocr_page") - 1
            page_result = ocr_results[page_idx]
            if isinstance(page_result, dict):
                blocks = page_result.get("blocks", page_result.get("text_blocks", []))
            elif isinstance(page_result, list):
                blocks = page_result
            else:
                blocks = []

            st.markdown(f"**第 {page_idx + 1} 页 OCR 文本**")
            for block in blocks:
                text = block.get("text", str(block)) if isinstance(block, dict) else str(block)
                conf = block.get("confidence", 1.0) if isinstance(block, dict) else 1.0
                if conf < threshold:
                    st.markdown(
                        f'<span style="background:#fff3e0; border-bottom:2px solid #f57c00; '
                        f'padding:2px 4px; border-radius:3px;" title="低置信度: {conf:.2f}">'
                        f'{escape_html(text)}</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.text(text)
        else:
            st.info("OCR 结果不可用")

    elif view_mode == "叠加视图":
        if not ocr_results:
            st.info("OCR 结果不可用")
            return

        page_idx = st.slider("选择页码", 1, min(len(image_paths), len(ocr_results)), 1, key="pdf_overlay_page") - 1

        col_img, col_text = st.columns([3, 2])
        with col_img:
            img_path = image_paths[page_idx]
            with open(img_path, "rb") as f:
                st.image(f.read(), caption=f"第 {page_idx + 1} 页原图", use_container_width=True)

        with col_text:
            st.markdown(f"**第 {page_idx + 1} 页 OCR 文本（叠加对照）**")
            page_result = ocr_results[page_idx]
            if isinstance(page_result, dict):
                blocks = page_result.get("blocks", page_result.get("text_blocks", []))
            elif isinstance(page_result, list):
                blocks = page_result
            else:
                blocks = []

            for block in blocks:
                text = block.get("text", str(block)) if isinstance(block, dict) else str(block)
                conf = block.get("confidence", 1.0) if isinstance(block, dict) else 1.0
                if conf < threshold:
                    st.markdown(
                        f'<div style="background:#fff3e0; border-left:3px solid #f57c00; '
                        f'padding:4px 8px; margin:2px 0; border-radius:4px; font-size:13px;">'
                        f'{escape_html(text)} '
                        f'<span style="color:#f57c00; font-size:10px;">(置信度: {conf:.2f})</span></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div style="padding:4px 8px; margin:2px 0; font-size:13px;">'
                        f'{escape_html(text)}</div>',
                        unsafe_allow_html=True,
                    )

        # 低置信度统计
        if low_confidence:
            lc_count = len(low_confidence) if isinstance(low_confidence, list) else 0
            if lc_count > 0:
                st.warning(f"⚠️ 当前页检测到 {lc_count} 个低置信度文本块，建议人工复核。")


# ============================================================
# Diff 热力图导航（增强版交互卡片）
# ============================================================

def _filter_diff_list(diff_list: list[dict]) -> list[dict]:
    """根据当前过滤状态筛选差异列表"""
    risk_filter = st.session_state.diff_filter_risk
    type_filter = st.session_state.diff_filter_type

    filtered = diff_list
    if risk_filter != "全部":
        filtered = [d for d in filtered if d["risk"] == risk_filter]
    if type_filter != "全部":
        filtered = [d for d in filtered if type_filter in d["type"]]
    return filtered


def render_diff_heatmap(diff_list: list[dict]) -> None:
    """渲染增强版差异热力图导航 — 可展开卡片列表"""
    st.markdown('<div class="panel-header">🔍 差异热力图导航</div>', unsafe_allow_html=True)

    # --- 过滤按钮（stateful） ---
    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
    risk_options = ["全部", "high", "medium", "low"]
    risk_labels = {"全部": "全部风险", "high": "🔴 高风险", "medium": "🟠 中风险", "low": "🟡 低风险"}
    for i, ro in enumerate(risk_options):
        with [col_r1, col_r2, col_r3, col_r4][i]:
            btn_type = "primary" if st.session_state.diff_filter_risk == ro else "secondary"
            if st.button(risk_labels[ro], key=f"risk_{ro}", use_container_width=True, type=btn_type):
                st.session_state.diff_filter_risk = ro
                st.session_state.selected_diff_idx = -1
                st.rerun()

    with col_r5:
        type_options = ["全部", "金额数字", "大写金额", "数字", "日期", "百分比"]
        selected_type = st.selectbox(
            "类型筛选",
            type_options,
            index=type_options.index(st.session_state.diff_filter_type)
            if st.session_state.diff_filter_type in type_options else 0,
            key="type_filter_select",
            label_visibility="collapsed",
        )
        if selected_type != st.session_state.diff_filter_type:
            st.session_state.diff_filter_type = selected_type
            st.session_state.selected_diff_idx = -1
            st.rerun()

    filtered = _filter_diff_list(diff_list)

    if not filtered:
        st.info("当前筛选条件下无差异项。")
        return

    st.caption(f"显示 {len(filtered)} / {len(diff_list)} 项差异")

    # --- 可展开卡片列表 ---
    for idx, d in enumerate(filtered):
        risk_color = {"high": "#d32f2f", "medium": "#f57c00", "low": "#1976d2"}[d["risk"]]
        risk_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}[d["risk"]]
        risk_label = {"high": "高风险", "medium": "中风险", "low": "低风险"}[d["risk"]]

        with st.expander(
            f"{risk_icon} [{d['type']}] {d['text'][:50]}{'...' if len(d['text']) > 50 else ''}",
            expanded=(idx == st.session_state.selected_diff_idx),
        ):
            # 点击展开时更新选中索引
            if idx != st.session_state.selected_diff_idx:
                st.session_state.selected_diff_idx = idx

            st.markdown(f"""
            <div style="display:flex; gap:12px; margin-bottom:12px; flex-wrap:wrap; align-items:center;">
                <span style="background:{risk_color}; color:#fff; padding:2px 10px; border-radius:10px;
                             font-size:0.75rem; font-weight:600;">{risk_label}</span>
                <span style="background:#f0f0f0; padding:2px 10px; border-radius:10px;
                             font-size:0.75rem; color:#555;">{escape_html(d["type"])}</span>
            </div>
            """, unsafe_allow_html=True)

            # 差异值
            st.markdown(f"""
            <div style="padding:10px; background:#fafafa; border-radius:6px; margin-bottom:10px;
                        font-size:1.05rem; font-weight:600; color:#333;">
                {escape_html(d["text"])}
            </div>
            """, unsafe_allow_html=True)

            # 上下文
            if d.get("phrase"):
                st.markdown(f"""
                <div style="padding:8px 12px; background:#f0f4ff; border-radius:6px; margin-bottom:10px;
                            font-size:0.85rem; color:#555; border-left:3px solid #1976d2;">
                    📍 上下文: {escape_html(d["phrase"])}
                </div>
                """, unsafe_allow_html=True)

            # Word vs PDF 侧侧对比
            word_text = st.session_state.get("word_text", "")
            pdf_text = st.session_state.get("pdf_text", "")
            if word_text and d["text"]:
                # 在原文中查找上下文
                context_before = ""
                context_after = ""
                search_text = d["text"]
                pos = word_text.find(search_text)
                if pos >= 0:
                    start = max(0, pos - 30)
                    end = min(len(word_text), pos + len(search_text) + 30)
                    before_raw = word_text[start:pos]
                    after_raw = word_text[pos + len(search_text):end]
                    context_before = f"...{escape_html(before_raw)}"
                    context_after = f"{escape_html(after_raw)}..."
                else:
                    pos_pdf = pdf_text.find(search_text)
                    if pos_pdf >= 0:
                        start = max(0, pos_pdf - 30)
                        end = min(len(pdf_text), pos_pdf + len(search_text) + 30)
                        before_raw = pdf_text[start:pos_pdf]
                        after_raw = pdf_text[pos_pdf + len(search_text):end]
                        context_before = f"...{escape_html(before_raw)}"
                        context_after = f"{escape_html(after_raw)}..."

                if context_before or context_after:
                    st.markdown("**📄 原文片段:**")
                    st.markdown(f"""
                    <div style="padding:10px 12px; background:#e3f2fd; border-radius:6px;
                                font-size:0.85rem; margin-bottom:4px;">
                        <span style="color:#999;">Word 原文: </span>{context_before}<mark style="background:#ffcdd2; padding:1px 3px;">{escape_html(search_text)}</mark>{context_after}
                    </div>
                    """, unsafe_allow_html=True)

                    # PDF 中对应位置
                    pos_pdf2 = pdf_text.find(search_text)
                    if pos_pdf2 >= 0:
                        pdf_start = max(0, pos_pdf2 - 30)
                        pdf_end = min(len(pdf_text), pos_pdf2 + len(search_text) + 30)
                        pdf_before = f"...{escape_html(pdf_text[pdf_start:pos_pdf2])}"
                        pdf_after = f"{escape_html(pdf_text[pos_pdf2 + len(search_text):pdf_end])}..."
                        st.markdown(f"""
                        <div style="padding:10px 12px; background:#e8f5e9; border-radius:6px;
                                    font-size:0.85rem;">
                            <span style="color:#999;">PDF 扫描件: </span>{pdf_before}<mark style="background:#c8e6c9; padding:1px 3px;">{escape_html(search_text)}</mark>{pdf_after}
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="padding:10px 12px; background:#ffebee; border-radius:6px;
                                    font-size:0.85rem; color:#c62828;">
                            ⚠️ 该差异项在 PDF 扫描件中未找到
                        </div>
                        """, unsafe_allow_html=True)

            # 位置指示
            st.caption(f"📌 差异项 #{idx + 1} · {d['risk']}风险 · {d['type']}")


# ============================================================
# 侧边栏
# ============================================================

def render_sidebar() -> None:
    """渲染侧边栏：设置、历史、配置管理"""
    with st.sidebar:
        st.markdown("## ⚙️ 控制面板")
        st.markdown("---")

        # ===== 行业预设 =====
        st.markdown("### 🏭 行业预设")
        industry_presets = ["通用", "租赁", "采购", "劳动", "工程"]
        selected_industry = st.selectbox("选择行业模板", industry_presets, key="industry_preset")
        if selected_industry != "通用":
            st.caption(f"已选择 {selected_industry} 行业预设模板")
        # 显示行业对应的字段类别
        industry_fields = _INDUSTRY_FIELDS.get(selected_industry, [])
        if industry_fields:
            fields_text = "、".join(industry_fields)
            st.caption(f"📋 检测字段：{fields_text}")

        # ===== 配置管理 =====
        st.markdown("### 📋 配置管理")
        col_cfg1, col_cfg2, col_cfg3 = st.columns(3)
        with col_cfg1:
            if st.button("新建配置", use_container_width=True, key="btn_new_profile"):
                st.toast("配置功能开发中，当前使用默认配置", icon="ℹ️")
        with col_cfg2:
            if st.button("保存配置", use_container_width=True, key="btn_save_profile"):
                st.toast("当前设置已保存到会话", icon="✅")
        with col_cfg3:
            if st.button("删除配置", use_container_width=True, key="btn_del_profile"):
                st.toast("请在设置中重置参数", icon="⚠️")

        st.markdown("---")

        # ===== 高级设置 =====
        st.markdown("### 🔧 高级设置")
        with st.expander("OCR 与比对参数", expanded=False):
            ocr_threshold = st.slider(
                "OCR 置信度阈值",
                min_value=0.3,
                max_value=0.9,
                value=st.session_state.ocr_confidence_threshold,
                step=0.05,
                key="ocr_threshold_slider",
                help="低于此阈值的 OCR 文本块将被标记为需复核",
            )
            if ocr_threshold != st.session_state.ocr_confidence_threshold:
                st.session_state.ocr_confidence_threshold = ocr_threshold

            comp_tolerance = st.slider(
                "比对容差",
                min_value=0.0,
                max_value=0.1,
                value=st.session_state.comparison_tolerance,
                step=0.005,
                key="comp_tolerance_slider",
                help="数字比对时的容差（如 0.01 表示允许 1% 误差）",
            )
            if comp_tolerance != st.session_state.comparison_tolerance:
                st.session_state.comparison_tolerance = comp_tolerance

        with st.expander("功能开关", expanded=False):
            # LLM Provider 选择
            llm_provider = st.selectbox(
                "LLM 服务提供商",
                ["Ollama (本地)", "Claude API"],
                index=0 if st.session_state.llm_provider == "ollama" else 1,
                key="llm_provider_select",
                help="选择 AI 语义分析使用的 LLM 后端",
            )
            # 更新 provider 选择到 session state
            if llm_provider == "Ollama (本地)":
                st.session_state.llm_provider = "ollama"
            else:
                st.session_state.llm_provider = "claude"

            # Claude API Key 输入
            if st.session_state.llm_provider == "claude":
                claude_key = st.text_input(
                    "Claude API Key",
                    value=st.session_state.get("claude_api_key", ""),
                    type="password",
                    key="claude_api_key_input",
                    help="输入 Anthropic Claude API Key",
                )
                st.session_state.claude_api_key = claude_key

            # 显示当前 Provider 可用状态
            try:
                provider_name = st.session_state.llm_provider
                if provider_name == "claude":
                    has_key = bool(st.session_state.get("claude_api_key", ""))
                    if has_key:
                        st.markdown('<span style="color:#2e7d32;">🟢 Claude API：Key 已配置</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span style="color:#d32f2f;">🔴 Claude API：Key 未设置</span>', unsafe_allow_html=True)
                else:
                    # 检测 Ollama 可用性
                    try:
                        temp_engine = LLMEngine(provider="ollama")
                        ollama_ok = temp_engine.is_available()
                    except Exception:
                        ollama_ok = False
                    if ollama_ok:
                        st.markdown('<span style="color:#2e7d32;">🟢 Ollama：服务可用</span>', unsafe_allow_html=True)
                    else:
                        st.markdown('<span style="color:#f57c00;">🟠 Ollama：服务未启动</span>', unsafe_allow_html=True)
            except Exception:
                pass

            st.markdown("---")

            enable_llm = st.checkbox(
                "启用 LLM 语义分析",
                value=st.session_state.enable_llm,
                key="enable_llm_cb",
                help="使用 AI 模型进行语义层面的差异分析",
            )
            if enable_llm != st.session_state.enable_llm:
                st.session_state.enable_llm = enable_llm

            enable_full_diff = st.checkbox(
                "启用全文差异比对",
                value=st.session_state.enable_full_text_diff,
                key="enable_full_diff_cb",
                help="除了关键字段比对外，再对全文做逐行差异比对",
            )
            if enable_full_diff != st.session_state.enable_full_text_diff:
                st.session_state.enable_full_text_diff = enable_full_diff

            enable_mask = st.checkbox(
                "启用敏感数据脱敏",
                value=st.session_state.enable_sensitive_masking,
                key="enable_mask_cb",
                help="自动遮盖手机号、身份证、银行卡等敏感信息",
            )
            if enable_mask != st.session_state.enable_sensitive_masking:
                st.session_state.enable_sensitive_masking = enable_mask

        st.markdown("---")

        # ===== 数据库状态 =====
        st.markdown("### 💾 数据库状态")
        if _DATABASE_AVAILABLE:
            try:
                db = get_database()
                # 查询历史比对任务数量
                tasks = db.list_tasks(limit=1000)
                task_count = len(tasks)
                st.markdown(f'<span style="color:#2e7d32;">🟢 数据库已连接</span>', unsafe_allow_html=True)
                st.caption(f"历史比对记录：{task_count} 条")
                # 清理历史数据按钮
                if st.button("🗑️ 清理历史数据", use_container_width=True, key="btn_cleanup_db"):
                    result = db.run_auto_cleanup(task_max_age_hours=1, log_max_age_days=7)
                    st.toast(f"已清理：{result.get('tasks', 0)} 条任务、{result.get('audit_logs', 0)} 条日志", icon="✅")
                    st.rerun()
            except Exception as e:
                st.markdown(f'<span style="color:#d32f2f;">🔴 数据库连接失败</span>', unsafe_allow_html=True)
                st.caption(f"错误：{e}")
        else:
            st.markdown('<span style="color:#f57c00;">🟠 数据库模块不可用</span>', unsafe_allow_html=True)
            st.caption("请确认 database.py 存在且依赖已安装")

        st.markdown("---")

        # ===== 比对历史 =====
        st.markdown("### 📜 比对历史")
        history = st.session_state.comparison_history
        if history:
            for h in reversed(history[-10:]):  # 最多显示最近 10 条
                icon = "🔴" if h["has_critical"] else "🟡" if h["total_diffs"] > 0 else "🟢"
                label = f"{icon} [{h['date']} {h['timestamp']}] {h['word_name']} vs {h['pdf_name']}"
                if st.button(
                    label,
                    key=f"hist_{h['id']}",
                    use_container_width=True,
                    type="secondary" if h["id"] != st.session_state.active_history_idx else "primary",
                ):
                    _restore_from_history(h["id"])
                    st.rerun()
        else:
            st.caption("暂无比对历史")

        st.markdown("---")

        # ===== 关于 =====
        st.markdown("""
        <div style="text-align:center; color:#999; font-size:0.75rem; padding:10px 0;">
            <b>合同比对专业版 v4.0</b><br>
            本地离线 · 数据不上传<br>
            <span style="font-size:0.65rem;">© 2025 Contract Comparator</span>
        </div>
        """, unsafe_allow_html=True)


# ============================================================
# 主函数
# ============================================================

def main() -> None:
    init_session_state()

    # ===== 全局 CSS =====
    st.markdown("""
    <style>
    /* 顶部导航栏 */
    .top-bar {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: #ffffff;
        padding: 14px 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .top-bar h1 {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 1px;
    }
    .top-bar .version {
        font-size: 0.8rem;
        opacity: 0.7;
        background: rgba(255,255,255,0.1);
        padding: 4px 10px;
        border-radius: 12px;
    }

    /* 上传区域 */
    .upload-zone {
        background: #f8f9fb;
        border: 2px dashed #d0d5dd;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
    }
    .upload-zone h3 {
        margin: 0 0 12px 0;
        font-size: 1rem;
        color: #344054;
    }

    /* KPI 卡片 */
    .kpi-row {
        display: flex;
        gap: 12px;
        margin-bottom: 16px;
        flex-wrap: wrap;
    }
    .kpi-card {
        flex: 1;
        min-width: 120px;
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .kpi-card .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    .kpi-card .kpi-label {
        font-size: 0.8rem;
        color: #666;
        margin-top: 4px;
    }
    .kpi-card.danger .kpi-value { color: #d32f2f; }
    .kpi-card.warning .kpi-value { color: #f57c00; }
    .kpi-card.success .kpi-value { color: #2e7d32; }
    .kpi-card.info .kpi-value { color: #1976d2; }

    /* 风险评级横幅 */
    .risk-banner {
        padding: 12px 20px;
        border-radius: 8px;
        margin-bottom: 16px;
        font-weight: 600;
        font-size: 0.95rem;
    }
    .risk-banner.safe {
        background: linear-gradient(90deg, #e8f5e9, #c8e6c9);
        border: 1px solid #a5d6a7;
        color: #2e7d32;
    }
    .risk-banner.warn {
        background: linear-gradient(90deg, #fff3e0, #ffe0b2);
        border: 1px solid #ffcc80;
        color: #e65100;
    }
    .risk-banner.danger {
        background: linear-gradient(90deg, #ffebee, #ffcdd2);
        border: 1px solid #ef9a9a;
        color: #c62828;
    }

    /* 差异导航面板 */
    .diff-nav {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 12px;
        max-height: 60vh;
        overflow-y: auto;
    }
    .diff-nav h4 {
        margin: 0 0 10px 0;
        font-size: 0.9rem;
        color: #344054;
        padding-bottom: 8px;
        border-bottom: 1px solid #eee;
    }
    .diff-item {
        padding: 8px 10px;
        margin-bottom: 6px;
        border-radius: 6px;
        cursor: pointer;
        border-left: 3px solid transparent;
        transition: all 0.15s ease;
        font-size: 0.85rem;
    }
    .diff-item:hover {
        background: #f0f4ff;
    }
    .diff-item.high {
        border-left-color: #d32f2f;
        background: #fff5f5;
    }
    .diff-item.medium {
        border-left-color: #f57c00;
        background: #fff8f0;
    }
    .diff-item.low {
        border-left-color: #1976d2;
        background: #f0f7ff;
    }
    .diff-item .diff-type {
        font-weight: 600;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .diff-item.high .diff-type { color: #d32f2f; }
    .diff-item.medium .diff-type { color: #f57c00; }
    .diff-item.low .diff-type { color: #1976d2; }
    .diff-item .diff-text {
        font-weight: 700;
        margin-top: 2px;
    }
    .diff-item .diff-phrase {
        color: #888;
        font-size: 0.78rem;
        margin-top: 2px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* 高亮样式 */
    .hl-amount {
        background-color: #ffcdd2;
        padding: 1px 5px;
        border-radius: 3px;
        border-bottom: 2px solid #d32f2f;
        font-weight: 700;
        color: #b71c1c;
    }
    .hl-number {
        background-color: #ffe0b2;
        padding: 1px 5px;
        border-radius: 3px;
        border-bottom: 2px solid #f57c00;
        font-weight: 700;
        color: #e65100;
    }
    .hl-date {
        background-color: #fff9c4;
        padding: 1px 5px;
        border-radius: 3px;
        border-bottom: 2px solid #fbc02d;
        font-weight: 700;
        color: #f57f17;
    }
    .hl-percent {
        background-color: #e1bee7;
        padding: 1px 5px;
        border-radius: 3px;
        border-bottom: 2px solid #8e24aa;
        font-weight: 700;
        color: #6a1b9a;
    }

    /* 图例 */
    .legend-bar {
        display: flex;
        gap: 16px;
        padding: 10px 14px;
        background: #f8f9fb;
        border-radius: 6px;
        margin-bottom: 12px;
        flex-wrap: wrap;
        align-items: center;
        font-size: 0.82rem;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .legend-swatch {
        width: 18px;
        height: 12px;
        border-radius: 2px;
        border: 1px solid rgba(0,0,0,0.1);
    }
    .legend-swatch.amount { background: #ffcdd2; border-bottom: 2px solid #d32f2f; }
    .legend-swatch.number { background: #ffe0b2; border-bottom: 2px solid #f57c00; }
    .legend-swatch.date { background: #fff9c4; border-bottom: 2px solid #fbc02d; }
    .legend-swatch.percent { background: #e1bee7; border-bottom: 2px solid #8e24aa; }

    /* 过滤按钮 */
    .filter-row {
        display: flex;
        gap: 6px;
        margin-bottom: 10px;
        flex-wrap: wrap;
    }
    .filter-btn {
        padding: 4px 10px;
        border-radius: 14px;
        font-size: 0.75rem;
        border: 1px solid #d0d5dd;
        background: #fff;
        cursor: pointer;
        transition: all 0.15s;
    }
    .filter-btn:hover { background: #f0f4ff; }
    .filter-btn.active { background: #1976d2; color: #fff; border-color: #1976d2; }

    /* 面板标题 */
    .panel-header {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1a1a2e;
        padding: 10px 0;
        border-bottom: 2px solid #e0e0e0;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .panel-header .badge {
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 10px;
        background: #e3f2fd;
        color: #1565c0;
        font-weight: 600;
    }

    /* 全文差异比对 */
    .full-text-diff {
        max-height: 60vh;
        overflow-y: auto;
        padding: 8px;
    }
    .full-text-diff .diff-item {
        padding: 10px 12px;
        margin-bottom: 8px;
        border-radius: 6px;
        border-left: 3px solid transparent;
        background: #fff;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .full-text-diff .diff-item.diff-high {
        border-left-color: #d32f2f;
        background: #fff5f5;
    }
    .full-text-diff .diff-item.diff-medium {
        border-left-color: #f57c00;
        background: #fff8f0;
    }
    .full-text-diff .diff-item.diff-low {
        border-left-color: #1976d2;
        background: #f0f7ff;
    }
    .full-text-diff .diff-header {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 6px;
    }
    .full-text-diff .diff-type {
        font-size: 0.7rem;
        padding: 2px 8px;
        border-radius: 10px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .full-text-diff .diff-type.diff-insert {
        background: #e8f5e9;
        color: #2e7d32;
    }
    .full-text-diff .diff-type.diff-delete {
        background: #ffebee;
        color: #c62828;
    }
    .full-text-diff .diff-category {
        font-size: 0.7rem;
        color: #666;
        background: #f0f0f0;
        padding: 2px 6px;
        border-radius: 8px;
    }
    .full-text-diff .diff-risk {
        font-size: 0.65rem;
        font-weight: 700;
        color: #999;
    }
    .full-text-diff .diff-content {
        font-size: 0.85rem;
        padding: 6px 8px;
        background: rgba(0,0,0,0.03);
        border-radius: 4px;
        margin-bottom: 4px;
        word-break: break-all;
    }
    .full-text-diff .diff-context {
        font-size: 0.75rem;
        color: #888;
        display: flex;
        gap: 4px;
    }
    .full-text-diff .context-before,
    .full-text-diff .context-after {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* LLM 语义分析 */
    .llm-report {
        padding: 12px;
    }
    .llm-summary {
        background: linear-gradient(135deg, #f3e5f5, #e1bee7);
        border: 1px solid #ce93d8;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .llm-summary h4 {
        margin: 0 0 8px 0;
        color: #6a1b9a;
        font-size: 1rem;
    }
    .llm-summary p {
        margin: 0 0 12px 0;
        font-size: 0.9rem;
        color: #4a148c;
    }
    .confidence-bar {
        height: 6px;
        background: #e0e0e0;
        border-radius: 3px;
        overflow: hidden;
        margin-bottom: 4px;
    }
    .confidence-fill {
        height: 100%;
        background: linear-gradient(90deg, #7b1fa2, #ab47bc);
        border-radius: 3px;
        transition: width 0.3s ease;
    }
    .confidence-label {
        font-size: 0.75rem;
        color: #6a1b9a;
        font-weight: 600;
    }
    .risk-items {
        margin-bottom: 16px;
    }
    .risk-item {
        padding: 12px;
        margin-bottom: 10px;
        border-radius: 6px;
        border-left: 3px solid transparent;
        background: #fff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .risk-item.risk-high {
        border-left-color: #d32f2f;
        background: #fff5f5;
    }
    .risk-item.risk-medium {
        border-left-color: #f57c00;
        background: #fff8f0;
    }
    .risk-item.risk-low {
        border-left-color: #1976d2;
        background: #f0f7ff;
    }
    .risk-item .risk-header {
        display: flex;
        gap: 8px;
        align-items: center;
        margin-bottom: 6px;
    }
    .risk-item .risk-type {
        font-size: 0.75rem;
        font-weight: 600;
        color: #333;
        background: #f0f0f0;
        padding: 2px 8px;
        border-radius: 10px;
    }
    .risk-item .risk-severity {
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 8px;
    }
    .risk-item.risk-high .risk-severity {
        background: #ffcdd2;
        color: #c62828;
    }
    .risk-item.risk-medium .risk-severity {
        background: #ffe0b2;
        color: #e65100;
    }
    .risk-item.risk-low .risk-severity {
        background: #bbdefb;
        color: #1565c0;
    }
    .risk-item .risk-description {
        font-size: 0.85rem;
        margin-bottom: 8px;
        color: #333;
    }
    .risk-item .risk-comparison {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 0.8rem;
    }
    .risk-item .risk-word {
        padding: 4px 8px;
        background: #e3f2fd;
        border-radius: 4px;
        color: #1565c0;
    }
    .risk-item .risk-pdf {
        padding: 4px 8px;
        background: #e8f5e9;
        border-radius: 4px;
        color: #2e7d32;
    }
    .llm-conclusion {
        background: #f5f5f5;
        border-radius: 6px;
        padding: 12px;
        font-size: 0.9rem;
        color: #333;
    }

    /* 差异概览卡片 */
    .diff-summary-card {
        background: #fff;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-left: 4px solid #d32f2f;
    }
    .diff-summary-card.warn { border-left-color: #f57c00; }
    .diff-summary-card.safe { border-left-color: #2e7d32; }
    .diff-summary-card .diff-count { font-size: 2rem; font-weight: 700; color: #d32f2f; }
    .diff-summary-card.warn .diff-count { color: #f57c00; }
    .diff-summary-card.safe .diff-count { color: #2e7d32; }

    /* 导出下载链接 */
    .download-link {
        display: inline-block;
        padding: 6px 12px;
        background: #1976d2;
        color: #fff !important;
        border-radius: 4px;
        text-decoration: none;
        font-size: 0.85rem;
        margin: 2px;
    }
    .download-link:hover {
        background: #1565c0;
        color: #fff !important;
    }

    /* 时间统计 */
    .timing-row {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin: 8px 0;
    }
    .timing-chip {
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        background: #e3f2fd;
        color: #1565c0;
        font-weight: 500;
    }
    </style>
    """, unsafe_allow_html=True)

    # ===== 顶部导航栏 =====
    st.markdown("""
    <div class="top-bar">
        <h1>📋 合同比对专业版</h1>
        <span class="version">v4.0 · 本地离线</span>
    </div>
    """, unsafe_allow_html=True)

    # ===== 渲染侧边栏 =====
    render_sidebar()

    # ===== 时间统计条（如果有统计数据） =====
    timing = st.session_state.timing_stats
    if timing:
        chips = "".join(
            f'<span class="timing-chip">{label}: {val}s</span>'
            for label, val in timing.items()
        )
        st.markdown(f'<div class="timing-row">{chips}</div>', unsafe_allow_html=True)

    # ===== 上传区域 =====
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown('<div class="upload-zone"><h3>📝 原版 Word 文档</h3></div>', unsafe_allow_html=True)
        word_file = st.file_uploader("上传 .docx 文件", type=["docx"], label_visibility="collapsed", key="word_uploader")
        if word_file:
            st.caption(f"已选择: **{word_file.name}** ({word_file.size / 1024:.1f} KB)")
    with col_b:
        st.markdown('<div class="upload-zone"><h3>📄 扫描件 PDF</h3></div>', unsafe_allow_html=True)
        pdf_file = st.file_uploader("上传 .pdf 文件", type=["pdf"], label_visibility="collapsed", key="pdf_uploader")
        if pdf_file:
            st.caption(f"已选择: **{pdf_file.name}** ({pdf_file.size / 1024:.1f} KB)")
    with col_c:
        st.markdown('<div class="upload-zone"><h3>🖼️ 扫描件图片</h3></div>', unsafe_allow_html=True)
        image_file = st.file_uploader(
            "上传图片文件",
            type=_IMAGE_EXTENSIONS,
            label_visibility="collapsed",
            key="image_uploader",
        )
        if image_file:
            st.caption(f"已选择: **{image_file.name}** ({image_file.size / 1024:.1f} KB)")

    # 合并 PDF 和图片上传（图片优先，作为扫描件输入）
    scan_file = image_file or pdf_file

    # 比对按钮 + 重试按钮
    btn_col, retry_col, _ = st.columns([1, 1, 2])
    with btn_col:
        can_compare = word_file is not None and scan_file is not None
        if st.button("🚀 开始比对", type="primary", use_container_width=True, disabled=not can_compare):
            st.session_state.running = True
            assert word_file is not None and scan_file is not None
            with tempfile.TemporaryDirectory() as tmpdir:
                word_path = os.path.join(tmpdir, word_file.name)
                scan_path = os.path.join(tmpdir, scan_file.name)
                with open(word_path, "wb") as f:
                    f.write(word_file.getvalue())
                with open(scan_path, "wb") as f:
                    f.write(scan_file.getvalue())
                success = run_comparison(word_path, scan_path, tmpdir)
            st.session_state.running = False
            if success:
                st.rerun()
    with retry_col:
        # 重试按钮（仅在出错时显示）
        if st.session_state.get("last_error"):
            if st.button("🔄 重试", use_container_width=True, key="retry_btn"):
                st.session_state.last_error = None
                st.rerun()

    # ===== 结果展示 =====
    if st.session_state.summary:
        summary = st.session_state.summary
        comparison_result = st.session_state.comparison_result
        diff_list = st.session_state.diff_list

        # 敏感数据脱敏（如果启用）
        if st.session_state.enable_sensitive_masking:
            if _SECURITY_AVAILABLE:
                st.info("🔒 敏感数据脱敏已启用 — 手机号、身份证、银行卡等将被遮盖")
            else:
                st.warning("🔒 安全模块不可用，脱敏功能无法生效")

        # 风险评级
        if summary["total_diffs"] == 0:
            st.markdown('<div class="risk-banner safe">✅ 所有关键字段一致，未发现差异</div>', unsafe_allow_html=True)
        elif summary["has_critical_diff"]:
            st.markdown(
                f'<div class="risk-banner danger">⚠️ 发现 <b>{summary["total_diffs"]}</b> 处差异，'
                f'涉及：{"、".join(d["type"] for d in summary["diff_details"])} — 金额差异需重点核查！</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div class="risk-banner warn">📌 发现 <b>{summary["total_diffs"]}</b> 处差异，'
                f'涉及：{"、".join(d["type"] for d in summary["diff_details"])}</div>',
                unsafe_allow_html=True
            )

        # KPI 卡片
        matched_count = sum(
            len(comparison_result[k].get("matched", []))
            for k in ["numbers", "dates", "amounts_words", "amounts_digits", "percentages"]
        )
        amount_diffs = len(comparison_result["amounts_digits"].get("missing_in_pdf", [])) + \
                       len(comparison_result["amounts_words"].get("missing_in_pdf", []))
        date_diffs = len(comparison_result["dates"].get("missing_in_pdf", []))
        number_diffs = len(comparison_result["numbers"].get("missing_in_pdf", []))

        st.markdown(f"""
        <div class="kpi-row">
            <div class="kpi-card info">
                <p class="kpi-value">{summary["total_diffs"]}</p>
                <p class="kpi-label">总差异</p>
            </div>
            <div class="kpi-card danger">
                <p class="kpi-value">{amount_diffs}</p>
                <p class="kpi-label">金额差异</p>
            </div>
            <div class="kpi-card warning">
                <p class="kpi-value">{date_diffs + number_diffs}</p>
                <p class="kpi-label">数字/日期差异</p>
            </div>
            <div class="kpi-card success">
                <p class="kpi-value">{matched_count}</p>
                <p class="kpi-label">匹配项</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ===== 主 Tab：核心视图 =====
        tab_overview, tab_diffmap, tab_pdfocr, tab_excel, tab_export = st.tabs([
            "📄 文档对比", "🔍 差异热力图", "🖼️ PDF图片/OCR", "📊 Excel对比", "📦 导出报表",
        ])

        with tab_overview:
            # 双文档比对视图
            st.subheader("📄 文档比对视图")

            # 图例
            st.markdown("""
            <div style="display: flex; gap: 20px; margin-bottom: 16px; padding: 12px; background: #f8f9fb; border-radius: 8px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #ffcdd2; padding: 4px 10px; border-radius: 4px; font-weight: bold; color: #b71c1c;">金额</span>
                    <span style="color: #666;">金额差异</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #ffe0b2; padding: 4px 10px; border-radius: 4px; font-weight: bold; color: #e65100;">数字</span>
                    <span style="color: #666;">数字差异</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #fff9c4; padding: 4px 10px; border-radius: 4px; font-weight: bold; color: #f57f17;">日期</span>
                    <span style="color: #666;">日期差异</span>
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="background: #e1bee7; padding: 4px 10px; border-radius: 4px; font-weight: bold; color: #6a1b9a;">百分比</span>
                    <span style="color: #666;">百分比差异</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # 双栏对比视图
            col_word, col_pdf = st.columns(2)

            with col_word:
                st.markdown("""
                <div style="background: #fff; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px;">
                    <div style="font-weight: 600; color: #1565c0; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #1565c0;">📝 Word 原文（差异高亮）</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background: #fff; border-radius: 8px; border: 1px solid #e0e0e0; '
                    f'padding: 16px; max-height: 500px; overflow-y: auto; font-size: 14px; '
                    f'line-height: 1.8; white-space: pre-wrap;">'
                    f'{st.session_state.highlighted_word_html}</div>',
                    unsafe_allow_html=True,
                )

            with col_pdf:
                st.markdown("""
                <div style="background: #fff; border-radius: 8px; border: 1px solid #e0e0e0; padding: 16px;">
                    <div style="font-weight: 600; color: #2e7d32; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #2e7d32;">📄 PDF 扫描件（OCR识别）</div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background: #fff; border-radius: 8px; border: 1px solid #e0e0e0; '
                    f'padding: 16px; max-height: 500px; overflow-y: auto; font-size: 14px; '
                    f'line-height: 1.8; white-space: pre-wrap;">'
                    f'{st.session_state.pdf_display_text}</div>',
                    unsafe_allow_html=True,
                )

            # 操作按钮
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📥 导出 HTML 报告", use_container_width=True, key="export_html_btn"):
                    report_html = generate_export_report()
                    st.download_button(
                        label="点击下载报告",
                        data=report_html,
                        file_name="合同比对报告.html",
                        mime="text/html",
                        use_container_width=True,
                        key="dl_html_report",
                    )
            with col2:
                if st.button("🔄 重新比对", use_container_width=True):
                    for key in [
                        "word_text", "pdf_text", "comparison_result", "summary", "diff_list",
                        "highlighted_word_html", "pdf_display_text", "full_text_diff_result",
                        "llm_analysis_result", "timing_stats", "pdf_image_paths", "ocr_results",
                        "low_confidence",
                    ]:
                        if key in st.session_state:
                            del st.session_state[key]
                    st.rerun()

            # ===== 高级分析区域 =====
            st.markdown("---")
            st.markdown('<div class="panel-header">📊 高级分析</div>', unsafe_allow_html=True)

            tab_fulltext, tab_llm = st.tabs(["全文差异比对", "AI 语义分析"])

            with tab_fulltext:
                full_text_diff_result = st.session_state.full_text_diff_result
                if full_text_diff_result:
                    ft_summary = full_text_diff_result["summary"]

                    st.markdown(f"""
                    <div class="kpi-row">
                        <div class="kpi-card info">
                            <p class="kpi-value">{ft_summary['total_changes']}</p>
                            <p class="kpi-label">全文变更数</p>
                        </div>
                        <div class="kpi-card danger">
                            <p class="kpi-value">{ft_summary['deletions']}</p>
                            <p class="kpi-label">删除项</p>
                        </div>
                        <div class="kpi-card success">
                            <p class="kpi-value">{ft_summary['insertions']}</p>
                            <p class="kpi-label">新增项</p>
                        </div>
                        <div class="kpi-card {"danger" if ft_summary["has_risk"] else "success"}">
                            <p class="kpi-value">{"⚠️" if ft_summary["has_risk"] else "✅"}</p>
                            <p class="kpi-label">高风险</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    diffs = full_text_diff_result["diffs"]
                    if diffs:
                        diff_html_parts = ['<div class="full-text-diff">']
                        for diff in diffs[:50]:
                            risk_class = f"diff-{diff['risk_level']}"
                            type_label = "新增" if diff["type"] == "insert" else "删除"
                            type_class = "diff-insert" if diff["type"] == "insert" else "diff-delete"

                            diff_html_parts.append(f"""
                            <div class="diff-item {risk_class}">
                                <div class="diff-header">
                                    <span class="diff-type {type_class}">{type_label}</span>
                                    <span class="diff-category">{diff['category']}</span>
                                    <span class="diff-risk">{diff['risk_level'].upper()}</span>
                                </div>
                                <div class="diff-content">{escape_html(diff['text'][:200])}</div>
                                <div class="diff-context">
                                    <span class="context-before">...{escape_html(diff['context_before'][-30:])}</span>
                                    <span class="context-after">{escape_html(diff['context_after'][:30])}...</span>
                                </div>
                            </div>
                            """)
                        diff_html_parts.append('</div>')
                        st.markdown('\n'.join(diff_html_parts), unsafe_allow_html=True)
                    else:
                        st.info("全文比对未发现差异")
                else:
                    st.info("全文比对结果未生成（可能已在设置中关闭）")

            with tab_llm:
                llm_result = st.session_state.llm_analysis_result
                if llm_result:
                    confidence = llm_result.get("confidence", 0)
                    if confidence > 0:
                        st.markdown(f"""
                        <div class="llm-summary">
                            <h4>🤖 AI 语义分析</h4>
                            <p>{llm_result.get("analysis", "")}</p>
                            <div class="confidence-bar">
                                <div class="confidence-fill" style="width: {confidence * 100}%"></div>
                            </div>
                            <span class="confidence-label">置信度: {confidence * 100:.0f}%</span>
                        </div>
                        """, unsafe_allow_html=True)

                        risk_items = llm_result.get("risk_items", [])
                        if risk_items:
                            st.markdown('<div class="risk-items">', unsafe_allow_html=True)
                            for item in risk_items:
                                severity = item.get("severity", "medium")
                                risk_type = item.get("risk_type", "")
                                description = item.get("description", "")
                                word_text_val = item.get("word_text", "")
                                pdf_text_val = item.get("pdf_text", "")

                                st.markdown(f"""
                                <div class="risk-item risk-{severity}">
                                    <div class="risk-header">
                                        <span class="risk-type">{escape_html(risk_type)}</span>
                                        <span class="risk-severity">{severity.upper()}</span>
                                    </div>
                                    <div class="risk-description">{escape_html(description)}</div>
                                    <div class="risk-comparison">
                                        <div class="risk-word"><b>原文:</b> {escape_html(word_text_val)}</div>
                                        <div class="risk-pdf"><b>扫描件:</b> {escape_html(pdf_text_val)}</div>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                            st.markdown('</div>', unsafe_allow_html=True)
                        else:
                            st.success("AI 未发现语义层面的风险修改")

                        st.markdown(f"""
                        <div class="llm-conclusion">
                            <p><b>总体评估:</b> {escape_html(llm_result.get("summary", ""))}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.warning("LLM 服务未启用或分析失败")
                        provider_name = st.session_state.get("llm_provider", "ollama")
                        if provider_name == "claude":
                            st.caption("配置方法：在侧边栏「功能开关」中输入 Claude API Key。")
                        else:
                            st.caption("配置方法：在侧边栏「功能开关」中确认 Ollama 服务已启动，或切换到 Claude API。")
                else:
                    st.info("AI 语义分析未执行（可能已在设置中关闭）")

        with tab_diffmap:
            # 增强版差异热力图
            if diff_list:
                render_diff_heatmap(diff_list)
            else:
                st.success("✅ 未发现差异")

            # 同时保留原有的差异明细表格（简洁概览）
            st.markdown("---")
            st.subheader("📋 差异明细表")
            if diff_list:
                diff_table_data = []
                for d in diff_list:
                    risk_color_map = {"high": "🔴", "medium": "🟠", "low": "🟡"}
                    risk_label_map = {"high": "高风险", "medium": "中风险", "low": "低风险"}
                    diff_table_data.append({
                        "风险等级": f"{risk_color_map[d['risk']]} {risk_label_map[d['risk']]}",
                        "类型": d["type"],
                        "差异内容": d["text"],
                        "上下文": d.get("phrase", "")[:40] + "..."
                        if len(d.get("phrase", "")) > 40
                        else d.get("phrase", ""),
                    })

                st.dataframe(diff_table_data, use_container_width=True, hide_index=True)
            else:
                st.success("✅ 未发现差异")

        with tab_pdfocr:
            # PDF 原图 + OCR 叠加视图
            render_pdf_image_ocr_tab()

        with tab_excel:
            # Excel 电子表格比对
            st.subheader("📊 Excel 电子表格对比")
            if not _EXCEL_COMPARATOR_AVAILABLE:
                st.warning("Excel 对比模块不可用，请确认 `excel_comparator.py` 存在且 `openpyxl` 已安装")
                st.code("pip install openpyxl")
            else:
                excel_col1, excel_col2 = st.columns(2)
                with excel_col1:
                    st.markdown("**📁 文件 A（基准文件）**")
                    excel_a = st.file_uploader(
                        "上传 Excel 文件 A",
                        type=["xlsx"],
                        key="excel_a_uploader",
                    )
                    if excel_a:
                        st.caption(f"已选择: **{excel_a.name}** ({excel_a.size / 1024:.1f} KB)")
                with excel_col2:
                    st.markdown("**📁 文件 B（对比文件）**")
                    excel_b = st.file_uploader(
                        "上传 Excel 文件 B",
                        type=["xlsx"],
                        key="excel_b_uploader",
                    )
                    if excel_b:
                        st.caption(f"已选择: **{excel_b.name}** ({excel_b.size / 1024:.1f} KB)")

                # Excel 比对按钮
                excel_btn_col, _ = st.columns([1, 3])
                with excel_btn_col:
                    can_excel_compare = excel_a is not None and excel_b is not None
                    if st.button("📊 开始 Excel 对比", type="primary", use_container_width=True,
                                 disabled=not can_excel_compare, key="excel_compare_btn"):
                        try:
                            with tempfile.TemporaryDirectory() as tmpdir:
                                excel_a_path = os.path.join(tmpdir, excel_a.name)
                                excel_b_path = os.path.join(tmpdir, excel_b.name)
                                with open(excel_a_path, "wb") as f:
                                    f.write(excel_a.getvalue())
                                with open(excel_b_path, "wb") as f:
                                    f.write(excel_b.getvalue())

                                with st.status("正在执行 Excel 对比...", expanded=True) as excel_status:
                                    st.write("📊 正在解析和比对 Excel 文件...")
                                    comparator = ExcelComparator(tolerance=st.session_state.comparison_tolerance)
                                    excel_result = comparator.compare(excel_a_path, excel_b_path)
                                    st.session_state.excel_comparison_result = excel_result

                                excel_status.update(label="✅ Excel 对比完成！", state="complete")
                                st.rerun()
                        except Exception as e:
                            st.error(f"❌ Excel 对比失败：{e}")

                # 显示 Excel 对比结果
                excel_result = st.session_state.get("excel_comparison_result")
                if excel_result:
                    excel_summary = excel_result.get("summary", {})
                    st.markdown("---")

                    # 摘要 KPI
                    st.markdown(f"""
                    <div class="kpi-row">
                        <div class="kpi-card info">
                            <p class="kpi-value">{excel_summary.get('total_sheets_compared', 0)}</p>
                            <p class="kpi-label">比对工作表</p>
                        </div>
                        <div class="kpi-card {"danger" if excel_summary.get("has_critical_diff") else "success"}">
                            <p class="kpi-value">{excel_summary.get('total_differences', 0)}</p>
                            <p class="kpi-label">差异总数</p>
                        </div>
                        <div class="kpi-card {"danger" if excel_summary.get("has_critical_diff") else "success"}">
                            <p class="kpi-value">{"⚠️" if excel_summary.get("has_critical_diff") else "✅"}</p>
                            <p class="kpi-label">高风险差异</p>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 各工作表差异明细
                    for sheet_result in excel_result.get("sheets", []):
                        sheet_name = sheet_result["sheet_name"]
                        status = sheet_result["status"]
                        differences = sheet_result.get("differences", [])
                        stats = sheet_result.get("stats", {})

                        if status == "only_in_a":
                            st.warning(f"⚠️ 工作表 **{sheet_name}** 仅存在于文件 A 中")
                            continue
                        elif status == "only_in_b":
                            st.info(f"ℹ️ 工作表 **{sheet_name}** 仅存在于文件 B 中")
                            continue

                        with st.expander(
                            f"📋 {sheet_name} — "
                            f"新增 {stats.get('added_rows', 0)} 行 / "
                            f"删除 {stats.get('deleted_rows', 0)} 行 / "
                            f"修改 {stats.get('modified_cells', 0)} 单元格",
                            expanded=False,
                        ):
                            if differences:
                                # 颜色编码的差异表格
                                diff_table_data = []
                                for diff in differences:
                                    diff_type = diff.get("type", "")
                                    risk = diff.get("risk", "low")
                                    risk_icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}.get(risk, "⚪")
                                    type_label = {
                                        "cell_changed": "单元格变更",
                                        "row_added": "新增行",
                                        "row_deleted": "删除行",
                                        "row_moved": "行移动",
                                    }.get(diff_type, diff_type)

                                    # 格式化值用于显示
                                    def _fmt_val(val):
                                        if val is None:
                                            return ""
                                        if isinstance(val, list):
                                            return " | ".join(str(c) for c in val if c != "")
                                        return str(val)

                                    diff_table_data.append({
                                        "风险": f"{risk_icon} {risk}",
                                        "类型": type_label,
                                        "行": diff.get("row", ""),
                                        "列": diff.get("col_name", "") if diff.get("col", -1) >= 0 else "",
                                        "文件A": _fmt_val(diff.get("value_a")),
                                        "文件B": _fmt_val(diff.get("value_b")),
                                    })

                                st.dataframe(diff_table_data, use_container_width=True, hide_index=True)
                            else:
                                st.success("✅ 该工作表无差异")

                    # 下载差异报告
                    st.markdown("---")
                    st.markdown("### 📥 下载 Excel 差异报告")
                    try:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            diff_excel_path = os.path.join(tmpdir, "Excel比对差异报告.xlsx")
                            generate_excel_diff_report(excel_result, diff_excel_path)
                            with open(diff_excel_path, "rb") as f:
                                diff_excel_data = f.read()
                            st.download_button(
                                label="📥 下载差异报告 Excel",
                                data=diff_excel_data,
                                file_name="Excel比对差异报告.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True,
                                key="dl_excel_diff",
                            )
                    except Exception as e:
                        st.error(f"生成差异报告失败：{e}")

        with tab_export:
            # 多格式导出
            render_export_buttons()

            # 仍然保留 HTML 导出作为备份
            st.markdown("---")
            st.caption("备用导出方式（纯 HTML 报告）:")
            col_h1, _ = st.columns([1, 3])
            with col_h1:
                if st.button("📥 备选 HTML 导出", use_container_width=True, key="alt_html_export"):
                    report_html = generate_export_report()
                    st.download_button(
                        label="点击下载 HTML 报告",
                        data=report_html,
                        file_name="合同比对报告.html",
                        mime="text/html",
                        use_container_width=True,
                        key="alt_dl_html",
                    )

    else:
        # 初始状态
        st.markdown("""
        <div style="text-align:center; padding: 60px 20px; color: #666;">
            <h2 style="color: #1a1a2e;">欢迎使用合同比对专业版</h2>
            <p>上传原版 Word 文档和扫描件 PDF/图片，点击"开始比对"即可自动分析差异。</p>
            <p style="font-size: 0.85rem; color: #999;">支持 .docx、.pdf 及常见图片格式 · 纯本地运行 · 数据不上传</p>
        </div>
        """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()