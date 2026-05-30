"""
合同扫描件比对工具 - 主入口
支持：Word/PDF 比对、Excel 对比、图片 OCR、多模型 LLM、行业预设、SQLite 存储
"""
import argparse
import logging
import os
import sys
import time

from contract_comparator.config import (
    OUTPUT_CONFIG, LLM_CONFIG, DATABASE_CONFIG, INDUSTRY_CONFIG,
    IMAGE_CONFIG, EXCEL_CONFIG, setup_logging,
)
from contract_comparator.engine.pdf_processor import pdf_to_images
from contract_comparator.engine.ocr.engine import OCREngine
from contract_comparator.engine.ocr.industry import IndustryFieldRecognizer
from contract_comparator.engine.word_parser import WordParser
from contract_comparator.compare.field_extractor import FieldExtractor
from contract_comparator.compare.comparator import Comparator
from contract_comparator.compare.full_text_diff import FullTextDiff
from contract_comparator.llm.llm_engine import LLMEngine
from contract_comparator.export.report_generator import ReportGenerator
from contract_comparator.utils import validate_file, ensure_output_dir

logger = logging.getLogger(__name__)


def _run_word_pdf_compare(args):
    """执行 Word 与 PDF 比对流水线"""
    # 验证输入文件
    if not validate_file(args.word, ['.docx']):
        sys.exit(1)
    if not validate_file(args.pdf, ['.pdf']):
        sys.exit(1)

    # 设置输出目录
    output_dir = args.output or OUTPUT_CONFIG["output_dir"]
    ensure_output_dir(output_dir)
    logger.info(f"输出目录: {output_dir}")

    start_time = time.time()

    # ==================== 第一步：解析 Word 文档 ====================
    logger.info("[1/5] 解析 Word 文档...")
    try:
        word_parser = WordParser(args.word)
        word_result = word_parser.parse()
        word_text = word_result["full_text"]
        logger.info(f"  [OK] 提取到 {word_result['paragraph_count']} 个段落，"
              f"{word_result['table_count']} 个表格")
    except Exception as e:
        logger.error(f"  [ERROR] Word 解析失败: {e}")
        sys.exit(1)

    # ==================== 第二步：PDF 转图片 ====================
    logger.info("[2/5] 转换 PDF 为图片...")
    try:
        image_dir = os.path.join(output_dir, "images")
        image_paths = pdf_to_images(args.pdf, output_dir=image_dir)
    except Exception as e:
        logger.error(f"  [ERROR] PDF 转换失败: {e}")
        sys.exit(1)

    # ==================== 第三步：OCR 识别 ====================
    logger.info("[3/5] OCR 识别扫描件...")
    try:
        ocr_engine = OCREngine()
        ocr_results = ocr_engine.recognize_pdf(image_paths)

        # 上下文置信度提升
        if args.boost_ocr:
            pdf_text_tmp = ocr_engine.get_full_text(ocr_results)
            ocr_results = ocr_engine.boost_confidence_with_context(ocr_results, pdf_text_tmp)

        pdf_text = ocr_engine.get_full_text(ocr_results)
        low_confidence = ocr_engine.get_low_confidence_items(ocr_results)

        # 行业字段识别
        industry = args.industry or INDUSTRY_CONFIG.get("default_industry", "general")
        industry_fields = None
        if industry != "general":
            recognizer = IndustryFieldRecognizer(industry=industry)
            industry_fields = recognizer.recognize_fields(ocr_results)
            field_count = len(industry_fields.get("fields", []))
            logger.info(f"  [OK] 行业字段识别（{industry}）：{field_count} 个字段")

        logger.info(f"  [OK] 共识别 {len(ocr_results)} 个文本块")
        if low_confidence:
            logger.warning(f"  [WARN] {len(low_confidence)} 个低置信度文本块（需人工复核）")
    except Exception as e:
        logger.error(f"  [ERROR] OCR 识别失败: {e}")
        sys.exit(1)

    # ==================== 第四步：字段抽取 ====================
    logger.info("[4/5] 抽取关键字段...")
    extractor = FieldExtractor()

    word_fields = extractor.extract_all(word_text, source="word")
    logger.info(f"  Word 字段: "
          f"{len(word_fields['numbers'])} 个数字, "
          f"{len(word_fields['dates'])} 个日期, "
          f"{len(word_fields['amounts_words'])} 个大写金额, "
          f"{len(word_fields['amounts_digits'])} 个金额数字")

    pdf_fields = extractor.extract_all(pdf_text, source="pdf")
    logger.info(f"  PDF 字段: "
          f"{len(pdf_fields['numbers'])} 个数字, "
          f"{len(pdf_fields['dates'])} 个日期, "
          f"{len(pdf_fields['amounts_words'])} 个大写金额, "
          f"{len(pdf_fields['amounts_digits'])} 个金额数字")

    # ==================== 第五步：字段比对 ====================
    logger.info("[5/5] 执行字段比对...")
    comparator = Comparator()
    comparison_result = comparator.compare(word_fields, pdf_fields)
    summary = comparator.get_summary(comparison_result)

    # ==================== 第六步（可选）：全文差异比对 ====================
    full_text_diff_result = None
    if args.full_diff:
        logger.info("[6/6] 执行全文差异比对...")
        full_text_differ = FullTextDiff()
        full_text_diff_result = full_text_differ.compare(word_text, pdf_text)
        ft_summary = full_text_diff_result["summary"]
        logger.info(f"  [OK] 全文比对完成：{ft_summary['total_changes']} 处变更 "
              f"(删除 {ft_summary['deletions']}, 新增 {ft_summary['insertions']})")
        if ft_summary["has_risk"]:
            logger.warning("  [WARN] 存在高风险变更项")

    # ==================== 第七步（可选）：LLM 语义分析 ====================
    llm_analysis_result = None
    if args.llm_analyze:
        logger.info("[7/7] 执行 LLM 语义分析...")
        provider = args.llm_provider or LLM_CONFIG.get("default_provider", "ollama")
        llm_kwargs = {}
        if args.llm_provider == "claude" and args.llm_api_key:
            llm_kwargs["api_key"] = args.llm_api_key
        if args.model:
            llm_kwargs["model"] = args.model

        llm_engine = LLMEngine(provider=provider, **llm_kwargs)
        if llm_engine.is_available():
            diff_list = []
            for item in comparison_result.get("amounts_digits", {}).get("missing_in_pdf", []):
                diff_list.append({"type": "金额数字", "text": item["raw"]})
            llm_analysis_result = llm_engine.analyze_semantic_diff(
                word_text, pdf_text, field_diffs=diff_list
            )
            logger.info(f"  [OK] AI 语义分析完成（置信度: {llm_analysis_result.get('confidence', 0) * 100:.0f}%）")
            logger.info(f"  分析摘要: {llm_analysis_result.get('analysis', '')}")
        else:
            logger.warning("  [WARN] LLM 服务未启用或不可用，跳过语义分析")

    # ==================== 生成报告 ====================
    logger.info("生成报告...")
    report_gen = ReportGenerator(output_dir)

    report_paths = []
    if args.format in ["text", "both"]:
        txt_path = report_gen.generate_text_report(
            args.word, args.pdf, comparison_result, summary, low_confidence
        )
        report_paths.append(txt_path)
        logger.info(f"  [OK] 文本报告: {txt_path}")

    if args.format in ["json", "both"]:
        json_path = report_gen.generate_json_report(
            args.word, args.pdf, comparison_result, summary, low_confidence
        )
        report_paths.append(json_path)
        logger.info(f"  [OK] JSON 报告: {json_path}")

    # ==================== 存入数据库 ====================
    if DATABASE_CONFIG.get("enabled", True):
        try:
            from contract_comparator.database import DatabaseManager
            db = DatabaseManager()
            task_id = f"cli_{int(time.time())}"
            db.create_task(
                task_id=task_id,
                word_file=args.word,
                pdf_file=args.pdf,
            )
            db.update_task(
                task_id=task_id,
                status="completed",
                result_summary=f"差异{summary['total_diffs']}处"
            )
            logger.info(f"  [OK] 任务已存入数据库: {task_id}")
        except Exception as db_err:
            logger.warning(f"  [WARN] 数据库存储失败: {db_err}")

    # ==================== 输出摘要 ====================
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("比对完成")
    logger.info("=" * 60)
    logger.info(f"耗时: {elapsed:.1f} 秒")

    if summary["total_diffs"] == 0:
        logger.info("[OK] 所有关键字段一致，未发现差异")
    else:
        logger.warning(f"[WARN] 发现 {summary['total_diffs']} 处差异:")
        for detail in summary["diff_details"]:
            logger.warning(f"   * {detail['type']}: 缺失 {detail['missing']} 个, "
                  f"多出 {detail['extra']} 个")

        if summary["has_critical_diff"]:
            logger.error("[!!] 存在金额相关差异，请重点人工核查！")

    if low_confidence:
        logger.warning(f"[WARN] 另有 {len(low_confidence)} 处低置信度字段需人工复核")

    logger.info(f"\n报告已保存至: {output_dir}")
    logger.info("=" * 60)


def _run_excel_compare(args):
    """执行 Excel 对比"""
    from contract_comparator.compare.excel_comparator import ExcelComparator

    if not validate_file(args.excel_a, ['.xlsx']):
        sys.exit(1)
    if not validate_file(args.excel_b, ['.xlsx']):
        sys.exit(1)

    output_dir = args.output or OUTPUT_CONFIG["output_dir"]
    ensure_output_dir(output_dir)

    logger.info("=" * 60)
    logger.info("Excel 表格对比工具")
    logger.info("=" * 60)

    start_time = time.time()
    tolerance = args.numeric_tolerance or EXCEL_CONFIG.get("numeric_tolerance", 0.01)

    try:
        comparator = ExcelComparator(tolerance=tolerance)
        result = comparator.compare(args.excel_a, args.excel_b)
        elapsed = time.time() - start_time

        # 输出摘要
        summary = result["summary"]
        logger.info(f"对比完成，耗时 {elapsed:.1f}s")
        logger.info(f"共对比 {summary.get('total_sheets_compared', 0)} 个工作表，"
              f"发现 {summary.get('total_differences', 0)} 处差异")

        if summary.get("has_critical_diff"):
            logger.warning("[!!] 存在高风险差异（金额/日期变更），请重点核查！")

        # 生成差异报告
        report_path = os.path.join(output_dir, "excel_diff_report.xlsx")
        from excel_comparator import generate_diff_excel
        generate_diff_excel(result, report_path)
        logger.info(f"差异报告已保存至: {report_path}")

    except Exception as e:
        logger.error(f"Excel 对比失败: {e}")
        sys.exit(1)


def _run_image_ocr(args):
    """执行图片 OCR 识别"""
    _image_exts = IMAGE_CONFIG.get("supported_formats", [])
    ext = os.path.splitext(args.image)[1].lower()
    if ext not in _image_exts:
        logger.error(f"不支持的图片格式: {ext}（支持: {', '.join(_image_exts)}）")
        sys.exit(1)

    if not os.path.isfile(args.image):
        logger.error(f"文件不存在: {args.image}")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("图片 OCR 识别工具")
    logger.info("=" * 60)

    start_time = time.time()
    try:
        ocr_engine = OCREngine()

        # 选择识别方式
        if args.segmentation:
            ocr_results = ocr_engine.recognize_image_with_segmentation(args.image)
        else:
            ocr_results = ocr_engine.recognize_image_file(args.image)

        # 置信度提升
        full_text = ocr_engine.get_full_text(ocr_results)
        if args.boost_ocr:
            ocr_results = ocr_engine.boost_confidence_with_context(ocr_results, full_text)
            full_text = ocr_engine.get_full_text(ocr_results)

        low_confidence = [r for r in ocr_results if r.get("confidence", 1.0) < 0.6]

        # 行业字段识别
        industry = args.industry or "general"
        industry_fields = None
        if industry != "general":
            recognizer = IndustryFieldRecognizer(industry=industry)
            industry_fields = recognizer.recognize_fields(ocr_results)

        elapsed = time.time() - start_time
        logger.info(f"OCR 识别完成，耗时 {elapsed:.1f}s")
        logger.info(f"共识别 {len(ocr_results)} 个文本块，{len(low_confidence)} 个低置信度")

        if industry_fields:
            field_count = len(industry_fields.get("fields", []))
            logger.info(f"行业字段识别（{industry}）：{field_count} 个字段")

        # 输出文本
        output_dir = args.output or OUTPUT_CONFIG["output_dir"]
        ensure_output_dir(output_dir)
        txt_path = os.path.join(output_dir, "ocr_result.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        logger.info(f"识别结果已保存至: {txt_path}")

    except Exception as e:
        logger.error(f"图片 OCR 失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="合同与文档智能比对工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Word 与 PDF 比对
  python main.py --word 原版合同.docx --pdf 扫描件.pdf
  python main.py --word 原版.docx --pdf 扫描.pdf --use-llm --llm-provider ollama
  python main.py --word 原版.docx --pdf 扫描.pdf --llm-analyze --llm-provider claude --llm-api-key sk-xxx

  # Excel 对比
  python main.py --excel-a 原版.xlsx --excel-b 对比版.xlsx

  # 图片 OCR
  python main.py --image 扫描件.png --industry construction
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ---- Word/PDF 比对 ----
    wp_parser = subparsers.add_parser("compare", help="Word 与 PDF 比对")
    wp_parser.add_argument("--word", required=True, help="原版 Word 文档路径 (.docx)")
    wp_parser.add_argument("--pdf", required=True, help="扫描件 PDF 路径 (.pdf)")
    wp_parser.add_argument("--output", default=None, help="输出目录（默认: ./output）")
    wp_parser.add_argument("--format", choices=["text", "json", "both"], default="both",
                        help="报告格式（默认: both）")
    wp_parser.add_argument("--full-diff", action="store_true",
                        help="启用全文差异比对（兜底分析）")
    wp_parser.add_argument("--llm-analyze", action="store_true",
                        help="启用 LLM 语义分析")
    wp_parser.add_argument("--llm-provider", choices=["ollama", "claude"],
                        default=None, help="LLM 供应商（默认: 配置文件中的 default_provider）")
    wp_parser.add_argument("--llm-api-key", default=None,
                        help="Claude API Key（仅 claude 供应商需要）")
    wp_parser.add_argument("--model", default=None,
                        help="自定义 LLM 模型名称")
    wp_parser.add_argument("--industry", default=None,
                        choices=["general", "construction", "leasing", "procurement", "labor"],
                        help="行业预设（默认: general）")
    wp_parser.add_argument("--boost-ocr", action="store_true", default=True,
                        help="启用 OCR 上下文置信度提升（默认开启）")
    wp_parser.add_argument("--no-boost-ocr", action="store_true",
                        help="禁用 OCR 上下文置信度提升")

    # ---- Excel 对比 ----
    ex_parser = subparsers.add_parser("excel", help="Excel 表格对比")
    ex_parser.add_argument("--excel-a", required=True, help="原版 Excel 文件 (.xlsx)")
    ex_parser.add_argument("--excel-b", required=True, help="对比 Excel 文件 (.xlsx)")
    ex_parser.add_argument("--output", default=None, help="输出目录")
    ex_parser.add_argument("--numeric-tolerance", type=float, default=0.01,
                        help="数值容差（默认: 0.01）")

    # ---- 图片 OCR ----
    img_parser = subparsers.add_parser("ocr", help="图片 OCR 识别")
    img_parser.add_argument("--image", required=True, help="图片文件路径")
    img_parser.add_argument("--output", default=None, help="输出目录")
    img_parser.add_argument("--industry", default=None,
                        choices=["general", "construction", "leasing", "procurement", "labor"],
                        help="行业预设（默认: general）")
    img_parser.add_argument("--boost-ocr", action="store_true", default=True,
                        help="启用 OCR 上下文置信度提升（默认开启）")
    img_parser.add_argument("--segmentation", action="store_true",
                        help="启用低置信度区域二次分割识别")

    # 兼容旧版无子命令的调用方式
    parser.add_argument("--word", default=None, help="(兼容) 原版 Word 文档路径 (.docx)")
    parser.add_argument("--pdf", default=None, help="(兼容) 扫描件 PDF 路径 (.pdf)")
    parser.add_argument("--output", default=None, help="(兼容) 输出目录")
    parser.add_argument("--use-llm", action="store_true", help="(兼容) 启用 LLM 辅助")
    parser.add_argument("--model", default=None, help="(兼容) LLM 模型名称")
    parser.add_argument("--format", choices=["text", "json", "both"], default="both",
                        help="(兼容) 报告格式")
    parser.add_argument("--no-preprocess", action="store_true",
                        help="(兼容) 关闭 OpenCV 图像预处理")
    parser.add_argument("--full-diff", action="store_true",
                        help="(兼容) 启用全文差异比对")
    parser.add_argument("--llm-analyze", action="store_true",
                        help="(兼容) 启用 LLM 语义分析")
    parser.add_argument("--llm-provider", choices=["ollama", "claude"], default=None)
    parser.add_argument("--llm-api-key", default=None)
    parser.add_argument("--industry", default=None,
                        choices=["general", "construction", "leasing", "procurement", "labor"])
    parser.add_argument("--boost-ocr", action="store_true", default=True)
    parser.add_argument("--no-boost-ocr", action="store_true")
    parser.add_argument("--excel-a", default=None, help="原版 Excel 文件 (.xlsx)")
    parser.add_argument("--excel-b", default=None, help="对比 Excel 文件 (.xlsx)")
    parser.add_argument("--image", default=None, help="图片文件路径")
    parser.add_argument("--numeric-tolerance", type=float, default=0.01)
    parser.add_argument("--segmentation", action="store_true")

    args = parser.parse_args()

    # 处理 --no-boost-ocr 参数覆盖（与 --boost-ocr 互斥）
    if getattr(args, "no_boost_ocr", False):
        args.boost_ocr = False

    # 初始化日志
    setup_logging()

    # 路由到对应子命令
    if args.command == "excel":
        _run_excel_compare(args)
        return
    elif args.command == "ocr":
        _run_image_ocr(args)
        return
    elif args.command == "compare":
        _run_word_pdf_compare(args)
        return

    # 兼容旧版：无子命令时根据参数自动路由
    if args.excel_a and args.excel_b:
        _run_excel_compare(args)
    elif args.image:
        _run_image_ocr(args)
    elif args.word and args.pdf:
        _run_word_pdf_compare(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
