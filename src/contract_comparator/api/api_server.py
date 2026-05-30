"""
合同比对专业版 REST API 服务
FastAPI + Uvicorn 提供高性能异步 API
"""
import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    BackgroundTasks,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from contract_comparator.config import OUTPUT_CONFIG, AUTH_CONFIG, setup_logging
from contract_comparator.compare.comparator import Comparator
from contract_comparator.database import DatabaseManager
from contract_comparator.compare.excel_comparator import ExcelComparator, ExcelParser
from contract_comparator.compare.field_extractor import FieldExtractor
from contract_comparator.compare.full_text_diff import FullTextDiff
from contract_comparator.llm.llm_engine import LLMEngine
from contract_comparator.engine.ocr.engine import OCREngine
from contract_comparator.engine.ocr.industry import IndustryFieldRecognizer
from contract_comparator.engine.pdf_processor import pdf_to_images
from contract_comparator.export.report_exporter import (
    export_redline_docx,
    export_diff_excel,
    export_pdf_report,
    export_json_api,
    export_full_package,
)
from contract_comparator.utils import ensure_output_dir
from contract_comparator.engine.word_parser import WordParser
from contract_comparator.auth import (
    APIKeyManager,
    RBACManager,
    RateLimiter,
    init_auth,
    get_key_manager,
    get_rate_limiter,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
    PERMISSION_COMPARE,
    PERMISSION_EXPORT,
    PERMISSION_MANAGE_KEYS,
    PERMISSION_MANAGE_PROFILES,
    PERMISSION_VIEW_AUDIT,
)
from contract_comparator.security import AuditLogger, FileUploadValidator

# ============================================================
# 初始化
# ============================================================
setup_logging()
logger = logging.getLogger("api_server")

# ============================================================
# FastAPI 应用
# ============================================================
app = FastAPI(
    title="合同比对专业版 API",
    description="合同扫描件（PDF）与原版 Word 文档比对服务，支持字段抽取、差异检测、报告导出。",
    version="v4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "比对", "description": "核心比对接口（合同/Excel/图片OCR）"},
        {"name": "报告", "description": "报告下载接口"},
        {"name": "配置", "description": "比对配置文件与 LLM 供应商管理"},
        {"name": "认证", "description": "API Key 管理与权限控制"},
        {"name": "审计", "description": "审计日志查询"},
        {"name": "系统", "description": "健康检查、任务管理、数据清理"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8501",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Pydantic 模型
# ============================================================
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_BATCH_PAIRS = 10


class DiffDetail(BaseModel):
    type: str
    missing: int
    extra: int


class SummaryOut(BaseModel):
    total_diffs: int
    has_critical_diff: bool
    diff_details: list[DiffDetail]


class FieldDetail(BaseModel):
    numbers: Optional[dict] = None
    dates: Optional[dict] = None
    amounts_words: Optional[dict] = None
    amounts_digits: Optional[dict] = None
    percentages: Optional[dict] = None


class CompareResult(BaseModel):
    task_id: str
    summary: SummaryOut
    diffs: FieldDetail
    full_text_diff: Optional[dict] = None
    llm_analysis: Optional[str] = None
    elapsed_seconds: float


class BatchCompareResult(BaseModel):
    task_id: str
    results: list[CompareResult]


class TaskStatusOut(BaseModel):
    task_id: str
    status: str  # pending / processing / completed / failed
    progress: float  # 0.0 ~ 100.0
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class HealthOut(BaseModel):
    service: str = "contract_comparator_api"
    version: str = "v4.0"
    status: str  # healthy / degraded / unhealthy
    dependencies: dict
    uptime_seconds: float


class DependencyStatus(BaseModel):
    ocr: bool
    word_parser: bool
    pdf_processor: bool
    llm: bool
    report_exporter: bool


class ProfileOut(BaseModel):
    name: str
    config: dict


class ProfileCreate(BaseModel):
    name: str
    config: dict


class ErrorResponse(BaseModel):
    detail: str
    error_code: int
    timestamp: str


# ---------- Excel 对比模型 ----------

class ExcelCompareRequest(BaseModel):
    """Excel 对比请求参数"""
    numeric_tolerance: float = 0.01
    include_hidden_sheets: bool = False


class ExcelSheetDiff(BaseModel):
    """单个工作表差异"""
    sheet_name: str
    status: str  # matched / only_in_a / only_in_b
    differences: list[dict]
    stats: dict


class ExcelCompareResult(BaseModel):
    """Excel 对比结果"""
    task_id: str
    summary: dict
    sheets: list[ExcelSheetDiff]
    elapsed_seconds: float


# ---------- 图片 OCR 模型 ----------

class ImageOCRRequest(BaseModel):
    """图片 OCR 请求参数"""
    industry: str = "general"
    boost_confidence: bool = True
    segmentation: bool = False  # 启用低置信度区域二次分割识别


class ImageOCRResult(BaseModel):
    """图片 OCR 结果"""
    task_id: str
    full_text: str
    ocr_items_count: int
    low_confidence_count: int
    industry_fields: Optional[dict] = None
    elapsed_seconds: float


# ---------- LLM 配置模型 ----------

class LLMProviderConfig(BaseModel):
    """LLM 供应商配置"""
    provider: str  # ollama / claude
    model: Optional[str] = None
    api_key: Optional[str] = None  # Claude API Key（仅 claude 供应商需要）
    base_url: Optional[str] = None  # Ollama base URL（仅 ollama 供应商需要）
    timeout: Optional[int] = None


class LLMProviderStatus(BaseModel):
    """LLM 供应商状态"""
    provider: str
    model: str
    available: bool
    message: Optional[str] = None


class LLMTestResult(BaseModel):
    """LLM 连通性测试结果"""
    provider: str
    model: str
    connected: bool
    response_preview: Optional[str] = None
    error: Optional[str] = None


# ---------- 数据库管理模型 ----------

class TaskListOut(BaseModel):
    """任务列表条目"""
    task_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    tasks: list[TaskListOut]


class CleanupRequest(BaseModel):
    """数据清理请求"""
    max_age_hours: int = 24
    cleanup_audit_logs: bool = False
    audit_max_age_days: int = 90


class CleanupResult(BaseModel):
    """数据清理结果"""
    tasks_deleted: int
    audit_logs_deleted: int
    message: str


# ---------- 比对请求增强模型 ----------

class CompareOptions(BaseModel):
    """比对选项（用于 JSON body 方式传参）"""
    use_llm: bool = False
    full_diff: bool = False
    llm_provider: Optional[str] = None  # ollama / claude
    llm_api_key: Optional[str] = None  # Claude API Key
    llm_model: Optional[str] = None  # 自定义模型名称
    industry: str = "general"  # 行业预设
    boost_ocr_confidence: bool = True  # 启用 OCR 上下文置信度提升
    ocr_segmentation: bool = False  # 启用低置信度区域二次分割


# ============================================================
# 内存存储：任务 & 配置文件
# ============================================================

class TaskStore:
    """线程安全的内存任务存储，支持 TTL 自动清理"""

    def __init__(self, ttl_seconds: int = 3600):
        self._lock = asyncio.Lock()
        self._tasks: dict[str, dict] = {}
        self._ttl = ttl_seconds

    async def create(self, task_id: str) -> None:
        async with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "status": "pending",
                "progress": 0.0,
                "result": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
            }

    async def update(self, task_id: str, **kwargs) -> None:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].update(kwargs)

    async def get(self, task_id: str) -> Optional[dict]:
        async with self._lock:
            return self._tasks.get(task_id)

    async def cleanup_expired(self) -> int:
        """清理过期任务，返回清理数量"""
        now = datetime.now(timezone.utc)
        expired = []
        async with self._lock:
            for tid, task in self._tasks.items():
                created = datetime.fromisoformat(task["created_at"])
                if (now - created).total_seconds() > self._ttl:
                    expired.append(tid)
            for tid in expired:
                del self._tasks[tid]
        if expired:
            logger.info(f"清理了 {len(expired)} 个过期任务")
        return len(expired)


class ProfileStore:
    """配置文件持久化存储"""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = asyncio.Lock()
        self._profiles: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        try:
            if os.path.exists(self._filepath):
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profiles = data.get("profiles", {})
                logger.info(f"加载了 {len(self._profiles)} 个比对配置文件")
        except Exception:
            self._profiles = {}

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump({"profiles": self._profiles}, f, ensure_ascii=False, indent=2)

    async def list_all(self) -> list[dict]:
        async with self._lock:
            return [{"name": k, "config": v} for k, v in self._profiles.items()]

    async def upsert(self, name: str, config: dict) -> None:
        async with self._lock:
            self._profiles[name] = config
            self._save()

    async def delete(self, name: str) -> bool:
        async with self._lock:
            if name in self._profiles:
                del self._profiles[name]
                self._save()
                return True
            return False

    async def get(self, name: str) -> Optional[dict]:
        async with self._lock:
            return self._profiles.get(name)


# 全局存储实例
task_store = TaskStore(ttl_seconds=3600)
output_dir = OUTPUT_CONFIG.get("output_dir", "./output")
profile_store = ProfileStore(os.path.join(output_dir, "profiles.json"))

# 数据库管理器（延迟初始化，在 startup 事件中创建）
db_manager: Optional[DatabaseManager] = None

# 认证与审计实例（延迟初始化，在 startup 事件中创建）
key_manager: Optional[APIKeyManager] = None
rate_limiter: Optional[RateLimiter] = None
audit_logger: Optional[AuditLogger] = None

# Config: bootstrap admin key auto-generation
_ALLOW_BOOTSTRAP_ADMIN_KEY = os.getenv("ALLOW_BOOTSTRAP_ADMIN_KEY", "false").lower() in ("true", "1", "yes")

# 服务启动时间
SERVICE_START_TIME = time.time()

# ============================================================
# 认证中间件与依赖注入
# ============================================================

async def get_api_key_from_request(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """仅从 Header 提取 API Key（Query 参数方式已移除，防止日志泄露）"""
    return x_api_key


def require_auth():
    """依赖注入：验证 API Key 并返回 key_info"""
    async def _verify(api_key_str: str = Depends(get_api_key_from_request)):
        global key_manager, rate_limiter

        if key_manager is None:
            # 认证未启用，跳过验证
            return None

        # 先验证 API Key 再限流（使用 Key ID + 角色作为标识，避免 Key 前缀泄露风险）
        key_info = key_manager.validate_key(api_key_str)
        if key_info is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的 API Key。",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # 速率限制检查
        if rate_limiter:
            client_id = f"{key_info.role}:{key_info.key_id}"
            if not rate_limiter.allow_request(client_id):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="请求频率过高，请稍后重试。",
                )

        return key_info
    return _verify


def require_permission(permission: str):
    """依赖注入：检查用户是否有指定权限"""
    async def _check(key_info = Depends(require_auth())):
        if key_info is None:
            # 认证未启用，允许访问
            return True
        if not RBACManager.has_permission(key_info.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足。需要权限: {permission}（当前角色: {key_info.role}）",
            )
        return True
    return _check


# ============================================================
# 比对核心引擎（可复用的同步流水线）
# ============================================================

def run_comparison_pipeline(
    word_path: str,
    pdf_path: str,
    use_llm: bool = False,
    full_diff: bool = False,
    profile_config: Optional[dict] = None,
) -> dict:
    """
    执行完整的比对流水线，返回结构化结果。
    此函数为同步函数，在 async 上下文中通过 run_in_executor 调用。
    """
    output_dir_local = os.path.join(
        OUTPUT_CONFIG.get("output_dir", "./output"), f"task_{uuid.uuid4().hex[:8]}"
    )
    ensure_output_dir(output_dir_local)

    # 第一步：解析 Word 文档
    word_parser = WordParser(word_path)
    word_result = word_parser.parse()
    word_text = word_result["full_text"]

    # 第二步：PDF 转图片
    image_dir = os.path.join(output_dir_local, "images")
    image_paths = pdf_to_images(pdf_path, output_dir=image_dir)

    # 第三步：OCR 识别
    ocr_engine = OCREngine()
    ocr_results = ocr_engine.recognize_pdf(image_paths)
    pdf_text = ocr_engine.get_full_text(ocr_results)
    low_confidence = ocr_engine.get_low_confidence_items(ocr_results)

    # 第四步：字段抽取
    extractor = FieldExtractor()
    word_fields = extractor.extract_all(word_text, source="word")
    pdf_fields = extractor.extract_all(pdf_text, source="pdf")

    # 第五步：字段比对
    comparator = Comparator()
    comparison_result = comparator.compare(word_fields, pdf_fields)
    summary = comparator.get_summary(comparison_result)

    # 第六步（可选）：全文差异比对
    full_text_diff_result = None
    if full_diff:
        full_text_differ = FullTextDiff()
        full_text_diff_result = full_text_differ.compare(word_text, pdf_text)

    # 第七步（可选）：LLM 语义分析
    llm_analysis_result = None
    if use_llm:
        llm_engine = LLMEngine()
        if llm_engine.is_available():
            diff_list = []
            for item in comparison_result.get("amounts_digits", {}).get("missing_in_pdf", []):
                diff_list.append({"type": "金额数字", "text": item["raw"]})
            llm_analysis_result = llm_engine.analyze_semantic_diff(
                word_text, pdf_text, field_diffs=diff_list
            )

    # 构建精简的 diffs 输出（去除冗余上下文）
    diffs_out = {}
    for key in ["numbers", "dates", "amounts_words", "amounts_digits", "percentages"]:
        section = comparison_result.get(key, {})
        diffs_out[key] = {
            "matched_count": len(section.get("matched", [])),
            "missing_in_pdf": [
                {"raw": item.get("raw", ""), "normalized": item.get("normalized", "")}
                for item in section.get("missing_in_pdf", [])
            ],
            "extra_in_pdf": [
                {"raw": item.get("raw", ""), "normalized": item.get("normalized", "")}
                for item in section.get("extra_in_pdf", [])
            ],
            "has_diff": section.get("has_diff", False),
        }

    # 构建摘要
    summary_out = {
        "total_diffs": summary["total_diffs"],
        "has_critical_diff": summary["has_critical_diff"],
        "diff_details": summary["diff_details"],
    }

    result = {
        "summary": summary_out,
        "diffs": diffs_out,
        "full_text_diff": full_text_diff_result,
        "llm_analysis": llm_analysis_result.get("analysis") if llm_analysis_result else None,
        "low_confidence_count": len(low_confidence),
        # 内部用：用于后续报告导出
        "_internal": {
            "comparison_result": comparison_result,
            "summary_raw": summary,
            "word_text": word_text,
            "pdf_text": pdf_text,
            "output_dir": output_dir_local,
        },
    }
    return result


# ============================================================
# 后台任务执行器
# ============================================================

async def _execute_compare_task(task_id: str, word_path: str, pdf_path: str,
                                 use_llm: bool, full_diff: bool,
                                 profile_config: Optional[dict]):
    """后台执行单个比对任务，更新 task_store"""
    start = time.time()
    try:
        await task_store.update(task_id, status="processing", progress=10.0)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            run_comparison_pipeline,
            word_path, pdf_path, use_llm, full_diff, profile_config,
        )
        await task_store.update(task_id, status="processing", progress=90.0)
        elapsed = time.time() - start

        # 存储内部数据供报告导出使用
        internal = result.pop("_internal", {})

        final_result = {
            "task_id": task_id,
            "summary": result["summary"],
            "diffs": result["diffs"],
            "full_text_diff": result.get("full_text_diff"),
            "llm_analysis": result.get("llm_analysis"),
            "elapsed_seconds": round(elapsed, 2),
        }
        await task_store.update(
            task_id,
            status="completed",
            progress=100.0,
            result=final_result,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
        # 将内部数据缓存到任务记录中
        if internal:
            async with task_store._lock:
                if task_id in task_store._tasks:
                    task_store._tasks[task_id]["_internal"] = internal
        logger.info(f"任务 {task_id} 完成，耗时 {elapsed:.1f}s")
    except Exception as e:
        logger.exception(f"任务 {task_id} 失败: {e}")
        await task_store.update(
            task_id,
            status="failed",
            error=str(e),
            completed_at=datetime.now(timezone.utc).isoformat(),
        )


# ============================================================
# FastAPI 生命周期
# ============================================================

@app.on_event("startup")
async def startup_event():
    """启动时初始化"""
    global SERVICE_START_TIME, key_manager, rate_limiter, audit_logger, db_manager
    SERVICE_START_TIME = time.time()

    # 初始化数据库管理器
    db_manager = DatabaseManager()
    logger.info("数据库管理器已初始化")

    # 初始化认证模块
    if AUTH_CONFIG.get("enabled", True):
        keys_file = AUTH_CONFIG.get("api_keys_file", "./config/api_keys.json")
        rl_config = AUTH_CONFIG.get("rate_limit", {})
        key_manager, rate_limiter = init_auth(
            keys_file=keys_file,
            rate_limit_enabled=rl_config.get("enabled", True),
            rpm=rl_config.get("requests_per_minute", 30),
            burst=rl_config.get("burst", 5),
        )

        # 如果没有 API Key，根据配置决定是否自动生成
        existing_keys = key_manager.list_keys()
        if not existing_keys:
            if not _ALLOW_BOOTSTRAP_ADMIN_KEY:
                logger.error(
                    "未配置任何 API Key，且 ALLOW_BOOTSTRAP_ADMIN_KEY 未启用。\n"
                    "请通过 contract-admin init-key 命令或设置环境变量 "
                    "ALLOW_BOOTSTRAP_ADMIN_KEY=true 来初始化管理员 Key。"
                )
                raise RuntimeError("缺少 API Key，启动失败。生产环境请使用显式初始化命令。")

            plain_key, key_id = key_manager.generate_key(ROLE_ADMIN, "default_admin")
            masked_key = f"{plain_key[:4]}...{plain_key[-4:]}"
            log_msg = (
                "首次启动：已生成默认管理员 API Key\n"
                f"  Key ID: {key_id}\n"
                f"  API Key (masked): {masked_key}\n"
                "  完整 Key 仅在首次生成的日志中可见（仅显示前4位+后4位）\n"
                "  请妥善保存此 Key，它仅在此处显示一次！"
            )
            logger.info(log_msg)
        else:
            logger.info(f"加载了 {len(existing_keys)} 个 API Key")
    else:
        logger.warning("认证模块已禁用！生产环境请勿禁用认证。")

    # 初始化审计日志
    audit_logger = AuditLogger(log_path=os.path.join(output_dir, "audit.log"))

    # 启动后台清理任务
    asyncio.create_task(_periodic_cleanup())
    logger.info("API 服务已启动")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理"""
    global db_manager
    # 关闭数据库连接
    if db_manager is not None:
        db_manager = None
        logger.info("数据库连接已关闭")
    logger.info("API 服务正在关闭")


async def _periodic_cleanup():
    """每 10 分钟清理过期任务"""
    while True:
        await asyncio.sleep(600)
        await task_store.cleanup_expired()


# ============================================================
# 通用错误处理
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    request_id = uuid.uuid4().hex[:12]
    logger.exception(f"未处理异常 [request_id={request_id}]: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "服务器内部错误，请稍后重试。",
            "error_code": 500,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


# ============================================================
# 辅助函数：文件验证与临时文件管理
# ============================================================

async def _save_upload_file(upload: UploadFile, prefix: str = "contract_",
                            allowed_exts: tuple = None) -> str:
    """将上传文件保存到临时目录，返回路径"""
    ext = Path(upload.filename).suffix.lower().lstrip(".") if upload.filename else ""
    _allowed = allowed_exts or ("docx", "pdf", "xlsx", "png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp")
    if ext not in _allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: .{ext}（支持: {', '.join('.' + e for e in _allowed)}）",
        )

    content = await upload.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_BYTES // (1024*1024)} MB）",
        )

    tmp_dir = tempfile.mkdtemp(prefix="contract_api_")
    filepath = os.path.join(tmp_dir, f"{prefix}.{ext}")

    with open(filepath, "wb") as f:
        f.write(content)

    # 魔数校验：验证文件真实类型与扩展名一致（严格模式）
    expected_ext = f".{ext}"
    validation = FileUploadValidator.validate_all(
        filepath,
        expected_types=[expected_ext],
        max_size_mb=MAX_UPLOAD_BYTES // (1024 * 1024),
        strict_unknown_magic=True,
    )
    if not validation.is_valid:
        _cleanup_temp_file(filepath)
        error_detail = "; ".join(validation.errors)
        logger.warning(f"文件校验失败 [{upload.filename}]: {error_detail}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"文件校验失败: {error_detail}",
        )

    logger.debug(f"临时文件已保存: {filepath} ({len(content)} bytes)")
    return filepath


def _cleanup_temp_file(filepath: str) -> None:
    """删除临时文件和目录"""
    try:
        tmp_dir = os.path.dirname(filepath)
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.debug(f"临时目录已删除: {tmp_dir}")
    except Exception:
        pass


# ============================================================
# API 端点
# ============================================================

# ---------- POST /api/v1/compare ----------

@app.post(
    "/api/v1/compare",
    response_model=CompareResult,
    tags=["比对"],
    summary="单次合同比对",
    description="上传一份 Word 文档和一份 PDF 扫描件，执行全流水线比对并返回结果。",
    responses={
        200: {"description": "比对成功"},
        400: {"description": "文件格式无效"},
        413: {"description": "文件过大"},
        500: {"description": "服务器错误"},
    },
)
async def compare_single(
    background_tasks: BackgroundTasks,
    word_file: UploadFile = File(..., description="原版 Word 文档 (.docx)"),
    pdf_file: UploadFile = File(..., description="扫描件 PDF (.pdf)"),
    use_llm: bool = Query(False, description="启用 LLM 语义分析"),
    full_diff: bool = Query(False, description="启用全文差异比对"),
    profile_name: Optional[str] = Form(None, description="比对配置文件名称"),
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_COMPARE)),
):
    if not word_file.filename or not pdf_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请同时上传 Word 文档和 PDF 文件",
        )

    # 获取配置文件（如果指定）
    profile_config = None
    if profile_name:
        profile_config = await profile_store.get(profile_name)
        if profile_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"比对配置文件不存在: {profile_name}",
            )

    # 保存上传文件
    word_path = await _save_upload_file(word_file, prefix="word")
    pdf_path = await _save_upload_file(pdf_file, prefix="pdf")

    # 生成任务 ID
    task_id = uuid.uuid4().hex[:12]

    # 记录审计日志
    user_id = key_info.key_id if key_info else "anonymous"
    if audit_logger:
        audit_logger.log_comparison(
            user_id=user_id,
            word_file=str(word_file.filename),
            pdf_file=str(pdf_file.filename),
            result_summary="比对任务已创建",
        )

    # 注册任务
    await task_store.create(task_id)

    # 同步执行（单次比对：让调用方等待结果）
    start = time.time()
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None,
        run_comparison_pipeline,
        word_path, pdf_path, use_llm, full_diff, profile_config,
    )
    elapsed = time.time() - start

    # 清理临时文件
    background_tasks.add_task(_cleanup_temp_file, word_path)
    background_tasks.add_task(_cleanup_temp_file, pdf_path)

    internal = result.pop("_internal", {})
    # 将内部数据存入任务存储（供后续报告下载）
    await task_store.update(
        task_id,
        status="completed",
        progress=100.0,
        result={
            "task_id": task_id,
            "summary": result["summary"],
            "diffs": result["diffs"],
            "full_text_diff": result.get("full_text_diff"),
            "llm_analysis": result.get("llm_analysis"),
            "elapsed_seconds": round(elapsed, 2),
        },
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
    if internal:
        async with task_store._lock:
            if task_id in task_store._tasks:
                task_store._tasks[task_id]["_internal"] = internal

    return CompareResult(
        task_id=task_id,
        summary=SummaryOut(**result["summary"]),
        diffs=FieldDetail(**result["diffs"]),
        full_text_diff=result.get("full_text_diff"),
        llm_analysis=result.get("llm_analysis"),
        elapsed_seconds=round(elapsed, 2),
    )


# ---------- POST /api/v1/compare/batch ----------

class BatchFilePair(BaseModel):
    word_file: str  # 由客户端传文件名标识
    pdf_file: str


@app.post(
    "/api/v1/compare/batch",
    tags=["比对"],
    summary="批量合同比对（异步）",
    description="上传多组 Word+PDF 文件对（最多 10 组），异步执行比对。返回 batch_task_id 用于轮询。",
    responses={
        200: {"description": "批量任务已创建"},
        400: {"description": "超过批量上限或文件格式错误"},
        500: {"description": "服务器错误"},
    },
)
async def compare_batch(
    background_tasks: BackgroundTasks,
    word_files: list[UploadFile] = File(..., description="Word 文档列表 (.docx)"),
    pdf_files: list[UploadFile] = File(..., description="PDF 扫描件列表 (.pdf)"),
    use_llm: bool = Query(False),
    full_diff: bool = Query(False),
    profile_name: Optional[str] = Form(None),
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_COMPARE)),
):
    n_pairs = min(len(word_files), len(pdf_files))
    if n_pairs == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一组文件",
        )
    if n_pairs > MAX_BATCH_PAIRS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"批量对比最多支持 {MAX_BATCH_PAIRS} 组文件对，当前 {n_pairs} 组",
        )

    # 获取配置文件
    profile_config = None
    if profile_name:
        profile_config = await profile_store.get(profile_name)
        if profile_config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"比对配置文件不存在: {profile_name}",
            )

    # 批量保存上传文件
    paths_pairs: list[tuple[str, str]] = []
    cleanup_paths: list[str] = []
    for i in range(n_pairs):
        wp = await _save_upload_file(word_files[i], prefix=f"word_{i}")
        pp = await _save_upload_file(pdf_files[i], prefix=f"pdf_{i}")
        paths_pairs.append((wp, pp))
        cleanup_paths.extend([wp, pp])

    # 创建批量任务
    batch_task_id = uuid.uuid4().hex[:12]
    child_task_ids = [uuid.uuid4().hex[:12] for _ in range(n_pairs)]

    await task_store.create(batch_task_id)
    await task_store.update(
        batch_task_id,
        status="processing",
        child_task_ids=child_task_ids,
        total=n_pairs,
        completed=0,
    )

    for i, (wp, pp) in enumerate(paths_pairs):
        child_id = child_task_ids[i]
        await task_store.create(child_id)
        # 启动后台异步任务
        asyncio.create_task(
            _execute_compare_task(
                child_id, wp, pp, use_llm, full_diff, profile_config,
            )
        )

    # 也启动一个监控任务来汇总子任务完成情况
    asyncio.create_task(
        _monitor_batch_tasks(batch_task_id, child_task_ids, cleanup_paths)
    )

    return {
        "batch_task_id": batch_task_id,
        "total_pairs": n_pairs,
        "child_task_ids": child_task_ids,
        "message": f"已创建 {n_pairs} 个比对子任务，请使用 /api/v1/compare/{{task_id}}/status 查询进度",
    }


async def _monitor_batch_tasks(batch_task_id: str, child_task_ids: list[str],
                                cleanup_paths: list[str]):
    """监控子任务，汇总到批量任务中"""
    while True:
        completed = 0
        failed = 0
        for cid in child_task_ids:
            t = await task_store.get(cid)
            if t and t["status"] in ("completed", "failed"):
                completed += 1
                if t["status"] == "failed":
                    failed += 1
        progress = round(completed / len(child_task_ids) * 100, 1) if child_task_ids else 100.0

        status = "completed" if completed == len(child_task_ids) else "processing"
        await task_store.update(
            batch_task_id,
            progress=progress,
            completed=completed,
            failed=failed,
            status=status,
        )

        if status == "completed":
            break
        await asyncio.sleep(1)

    # 批量清理临时文件
    for path in cleanup_paths:
        _cleanup_temp_file(path)


# ---------- GET /api/v1/compare/{task_id}/status ----------

@app.get(
    "/api/v1/compare/{task_id}/status",
    response_model=TaskStatusOut,
    tags=["比对"],
    summary="查询任务状态",
    description="根据任务 ID 查询异步比对任务的执行状态和结果。",
    responses={
        200: {"description": "任务状态"},
        404: {"description": "任务不存在"},
    },
)
async def get_task_status(
    task_id: str,
    key_info = Depends(require_auth()),
):
    task = await task_store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在: {task_id}",
        )
    return TaskStatusOut(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        result=task.get("result"),
        error=task.get("error"),
        created_at=task["created_at"],
        completed_at=task.get("completed_at"),
    )


# ---------- GET /api/v1/compare/{task_id}/report/{format} ----------

@app.get(
    "/api/v1/compare/{task_id}/report/{report_format}",
    tags=["报告"],
    summary="下载比对报告",
    description="根据已完成的任务 ID 下载指定格式的报告文件。",
    responses={
        200: {"description": "报告文件"},
        404: {"description": "任务不存在或未完成"},
        400: {"description": "不支持的格式"},
    },
)
async def download_report(
    task_id: str,
    report_format: str,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_EXPORT)),
):
    report_format = report_format.lower()
    if report_format not in ("docx", "xlsx", "pdf", "json", "zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的报告格式: {report_format}（支持: docx, xlsx, pdf, json, zip）",
        )

    task = await task_store.get(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在: {task_id}",
        )
    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务尚未完成（当前状态: {task['status']}），请等待完成后下载报告",
        )

    internal: dict = task.get("_internal", {})
    if not internal:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="任务缺少内部比对数据，无法生成报告",
        )

    comparison_result = internal["comparison_result"]
    summary_raw = internal["summary_raw"]
    word_text = internal["word_text"]
    pdf_text = internal["pdf_text"]

    content_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
        "json": "application/json",
        "zip": "application/zip",
    }
    file_exts = {
        "docx": "docx",
        "xlsx": "xlsx",
        "pdf": "pdf",
        "json": "json",
        "zip": "zip",
    }

    loop = asyncio.get_running_loop()

    try:
        if report_format == "docx":
            data = await loop.run_in_executor(
                None,
                export_redline_docx, comparison_result, summary_raw, word_text, pdf_text,
            )
        elif report_format == "xlsx":
            data = await loop.run_in_executor(
                None,
                export_diff_excel, comparison_result, summary_raw, word_text, pdf_text,
            )
        elif report_format == "pdf":
            data = await loop.run_in_executor(
                None,
                export_pdf_report, comparison_result, summary_raw, word_text, pdf_text,
            )
        elif report_format == "json":
            json_str = await loop.run_in_executor(
                None,
                export_json_api, comparison_result, summary_raw, word_text, pdf_text,
            )
            data = json_str.encode("utf-8")
        elif report_format == "zip":
            data = await loop.run_in_executor(
                None,
                export_full_package, comparison_result, summary_raw, word_text, pdf_text,
            )
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"生成报告失败 [{report_format}]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="生成报告失败，请稍后重试。",
        )

    filename = f"contract_diff_report_{task_id}.{file_exts[report_format]}"

    # 记录审计日志
    user_id = key_info.key_id if key_info else "anonymous"
    if audit_logger:
        audit_logger.log_export(
            user_id=user_id,
            format=report_format,
            file_path=filename,
        )

    return Response(
        content=data,
        media_type=content_types[report_format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- GET /api/v1/health ----------

@app.get(
    "/api/v1/health",
    response_model=HealthOut,
    tags=["系统"],
    summary="健康检查",
    description="返回服务健康状态、依赖项可用性及运行时间。",
)
async def health_check():
    deps = {}
    # 检查 OCR 引擎
    try:
        ocr = OCREngine()
        deps["ocr"] = True
    except Exception:
        deps["ocr"] = False

    # 检查 Word 解析器（使用导入可用性判断）
    try:
        from docx import Document
        deps["word_parser"] = True
    except Exception:
        deps["word_parser"] = False

    # 检查 PDF 处理器
    try:
        import fitz
        deps["pdf_processor"] = True
    except Exception:
        deps["pdf_processor"] = False

    # 检查 LLM
    try:
        llm = LLMEngine()
        deps["llm"] = llm.is_available()
    except Exception:
        deps["llm"] = False

    # 检查报告导出
    try:
        from report_exporter import export_json_api
        deps["report_exporter"] = True
    except Exception:
        deps["report_exporter"] = False

    all_ok = all(deps.values())
    critical_ok = all([deps.get("ocr", False), deps.get("word_parser", False), deps.get("pdf_processor", False)])

    if all_ok:
        health = "healthy"
    elif critical_ok:
        health = "degraded"
    else:
        health = "unhealthy"

    uptime = time.time() - SERVICE_START_TIME

    return HealthOut(
        status=health,
        dependencies=deps,
        uptime_seconds=round(uptime, 1),
    )


# ---------- 配置文件管理 ----------

@app.get(
    "/api/v1/profiles",
    response_model=list[ProfileOut],
    tags=["配置"],
    summary="列出比对配置文件",
    description="返回所有已保存的比对配置文件。",
)
async def list_profiles(
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_PROFILES)),
):
    profiles = await profile_store.list_all()
    return [ProfileOut(name=p["name"], config=p["config"]) for p in profiles]


@app.post(
    "/api/v1/profiles",
    response_model=ProfileOut,
    tags=["配置"],
    summary="创建/更新比对配置文件",
    description="保存一个比对配置文件（根据 name 覆盖已有或新建）。",
    responses={
        200: {"description": "配置文件已保存"},
        400: {"description": "参数无效"},
    },
)
async def upsert_profile(
    profile: ProfileCreate,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_PROFILES)),
):
    if not profile.name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="配置文件名称不能为空",
        )
    await profile_store.upsert(profile.name, profile.config)
    return ProfileOut(name=profile.name, config=profile.config)


@app.delete(
    "/api/v1/profiles/{name}",
    tags=["配置"],
    summary="删除比对配置文件",
    description="根据名称删除指定的比对配置文件。",
    responses={
        200: {"description": "配置文件已删除"},
        404: {"description": "配置文件不存在"},
    },
)
async def delete_profile(
    name: str,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_PROFILES)),
):
    deleted = await profile_store.delete(name)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"比对配置文件不存在: {name}",
        )
    return {"message": f"配置文件 '{name}' 已删除", "name": name}


# ============================================================
# API Key 管理（仅 admin）
# ============================================================

class APIKeyOut(BaseModel):
    key_id: str
    role: str
    label: str
    created_at: str
    last_used_at: Optional[str] = None
    is_active: bool


class APIKeyCreate(BaseModel):
    role: str
    label: str = ""


class APIKeyGenerateOut(BaseModel):
    key_id: str
    plain_key: str
    role: str
    label: str
    created_at: str
    warning: str = "请妥善保存此 Key，它仅在此处显示一次！"


@app.post(
    "/api/v1/auth/keys",
    response_model=APIKeyGenerateOut,
    tags=["认证"],
    summary="生成新的 API Key",
    description="生成一个新的 API Key（仅 admin 可访问）。",
    responses={
        200: {"description": "API Key 已生成"},
        400: {"description": "角色无效"},
        403: {"description": "权限不足"},
    },
)
async def generate_api_key(
    request: APIKeyCreate,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_KEYS)),
):
    global key_manager
    if key_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块未启用。",
        )

    if request.role not in (ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的角色: {request.role}（可选: {ROLE_ADMIN}, {ROLE_ANALYST}, {ROLE_VIEWER}）",
        )

    plain_key, key_id = key_manager.generate_key(request.role, request.label)

    # 记录审计日志
    if audit_logger:
        audit_logger._write_entry({
            "event": "api_key_created",
            "user_id": key_info.key_id,
            "new_key_id": key_id,
            "new_key_role": request.role,
        })

    return APIKeyGenerateOut(
        key_id=key_id,
        plain_key=plain_key,
        role=request.role,
        label=request.label or f"{request.role}_key_{key_id[:6]}",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/api/v1/auth/keys",
    response_model=list[APIKeyOut],
    tags=["认证"],
    summary="列出所有 API Key",
    description="列出所有 API Key（不返回明文，仅 admin 可访问）。",
    responses={
        200: {"description": "API Key 列表"},
        403: {"description": "权限不足"},
    },
)
async def list_api_keys(
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_KEYS)),
):
    global key_manager
    if key_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块未启用。",
        )

    keys = key_manager.list_keys()
    return [APIKeyOut(**k) for k in keys]


@app.delete(
    "/api/v1/auth/keys/{key_id}",
    tags=["认证"],
    summary="删除 API Key",
    description="删除指定的 API Key（仅 admin 可访问）。",
    responses={
        200: {"description": "API Key 已删除"},
        404: {"description": "API Key 不存在"},
        403: {"description": "权限不足"},
    },
)
async def delete_api_key(
    key_id: str,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_KEYS)),
):
    global key_manager
    if key_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块未启用。",
        )

    # 不能删除自己的 Key
    if key_id == key_info.key_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除当前使用的 API Key。",
        )

    deleted = key_manager.delete_key(key_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API Key 不存在: {key_id}",
        )

    # 记录审计日志
    if audit_logger:
        audit_logger._write_entry({
            "event": "api_key_deleted",
            "user_id": key_info.key_id,
            "deleted_key_id": key_id,
        })

    return {"message": f"API Key '{key_id}' 已删除", "key_id": key_id}


@app.post(
    "/api/v1/auth/keys/{key_id}/toggle",
    tags=["认证"],
    summary="启用/禁用 API Key",
    description="切换指定 API Key 的启用状态（仅 admin 可访问）。",
    responses={
        200: {"description": "API Key 状态已切换"},
        404: {"description": "API Key 不存在"},
        403: {"description": "权限不足"},
    },
)
async def toggle_api_key(
    key_id: str,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_KEYS)),
):
    global key_manager
    if key_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="认证模块未启用。",
        )

    toggled = key_manager.toggle_key(key_id)
    if not toggled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API Key 不存在: {key_id}",
        )

    return {"message": f"API Key '{key_id}' 状态已切换", "key_id": key_id}


# ============================================================
# 审计日志查询（仅 admin）
# ============================================================

class AuditQueryParams(BaseModel):
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    user_id: Optional[str] = None
    event: Optional[str] = None


@app.get(
    "/api/v1/audit/logs",
    tags=["审计"],
    summary="查询审计日志",
    description="查询审计日志记录（仅 admin 可访问）。",
    responses={
        200: {"description": "审计日志列表"},
        403: {"description": "权限不足"},
    },
)
async def query_audit_logs(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO 8601)"),
    user_id: Optional[str] = Query(None, description="用户 ID"),
    event: Optional[str] = Query(None, description="事件类型"),
    limit: int = Query(100, ge=1, le=1000, description="返回记录数上限"),
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_VIEW_AUDIT)),
):
    global audit_logger
    if audit_logger is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="审计模块未启用。",
        )

    start_dt = datetime.fromisoformat(start_time) if start_time else None
    end_dt = datetime.fromisoformat(end_time) if end_time else None

    records = audit_logger.get_audit_records(
        start_time=start_dt,
        end_time=end_dt,
        user_id=user_id,
        event=event,
    )

    return {
        "total": len(records),
        "records": records[:limit],
    }


# ============================================================
# Excel 对比接口
# ============================================================

@app.post(
    "/api/v1/compare/excel",
    response_model=ExcelCompareResult,
    tags=["比对"],
    summary="Excel 表格对比",
    description="上传两份 Excel 文件，执行逐单元格对比分析，返回差异结果。",
    responses={
        200: {"description": "对比成功"},
        400: {"description": "文件格式无效"},
        413: {"description": "文件过大"},
        500: {"description": "服务器错误"},
    },
)
async def compare_excel(
    background_tasks: BackgroundTasks,
    excel_a: UploadFile = File(..., description="原版 Excel 文件 (.xlsx)"),
    excel_b: UploadFile = File(..., description="对比 Excel 文件 (.xlsx)"),
    numeric_tolerance: float = Query(0.01, description="数值容差"),
    include_hidden_sheets: bool = Query(False, description="包含隐藏工作表"),
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_COMPARE)),
):
    if not excel_a.filename or not excel_b.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请同时上传两份 Excel 文件",
        )

    # 保存上传文件
    path_a = await _save_upload_file(excel_a, prefix="excel_a",
                                      allowed_exts=("xlsx",))
    path_b = await _save_upload_file(excel_b, prefix="excel_b",
                                      allowed_exts=("xlsx",))

    task_id = uuid.uuid4().hex[:12]
    start = time.time()

    try:
        loop = asyncio.get_running_loop()
        comparator = ExcelComparator(tolerance=numeric_tolerance)
        result = await loop.run_in_executor(
            None,
            comparator.compare,
            path_a, path_b,
        )
        elapsed = time.time() - start

        # 存入数据库
        if db_manager:
            try:
                db_manager.create_task(
                    task_id=task_id,
                    word_file=excel_a.filename,
                    pdf_file=excel_b.filename,
                    user_id=key_info.key_id if key_info else "anonymous",
                )
                db_manager.update_task(task_id, status="completed",
                                        result_summary=json.dumps(
                                            result["summary"], ensure_ascii=False))
            except Exception as db_err:
                logger.warning(f"数据库写入失败: {db_err}")

        # 记录审计日志
        if audit_logger:
            audit_logger._write_entry({
                "event": "excel_compare",
                "user_id": key_info.key_id if key_info else "anonymous",
                "file_a": str(excel_a.filename),
                "file_b": str(excel_b.filename),
            })

        return ExcelCompareResult(
            task_id=task_id,
            summary=result["summary"],
            sheets=[ExcelSheetDiff(**s) for s in result["sheets"]],
            elapsed_seconds=round(elapsed, 2),
        )
    except Exception as e:
        logger.exception(f"Excel 对比失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Excel 对比失败，请检查文件格式后重试。",
        )
    finally:
        background_tasks.add_task(_cleanup_temp_file, path_a)
        background_tasks.add_task(_cleanup_temp_file, path_b)


@app.get(
    "/api/v1/compare/excel/{task_id}/report",
    tags=["报告"],
    summary="下载 Excel 差异报告",
    description="根据已完成的 Excel 对比任务 ID 下载差异报告 Excel 文件。",
)
async def download_excel_diff_report(
    task_id: str,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_EXPORT)),
):
    """生成并下载 Excel 差异报告（颜色编码）"""
    # 此端点需要配合数据库存储的比对结果使用
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="请使用 /api/v1/compare/excel 直接比对后从返回结果中获取差异信息",
    )


# ============================================================
# 图片 OCR 接口
# ============================================================

@app.post(
    "/api/v1/ocr/image",
    response_model=ImageOCRResult,
    tags=["比对"],
    summary="图片 OCR 识别",
    description="上传一张图片文件，执行 OCR 识别并返回文本结果。支持行业字段识别。",
    responses={
        200: {"description": "识别成功"},
        400: {"description": "文件格式无效"},
        413: {"description": "文件过大"},
        500: {"description": "服务器错误"},
    },
)
async def ocr_image(
    background_tasks: BackgroundTasks,
    image_file: UploadFile = File(..., description="图片文件 (.png/.jpg/.bmp/.tiff/.webp)"),
    industry: str = Query("general", description="行业预设 (general/construction/leasing/procurement/labor)"),
    boost_confidence: bool = Query(True, description="启用上下文置信度提升"),
    segmentation: bool = Query(False, description="启用低置信度区域二次分割识别"),
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_COMPARE)),
):
    _image_exts = ("png", "jpg", "jpeg", "bmp", "tiff", "tif", "webp")
    path = await _save_upload_file(image_file, prefix="ocr_image",
                                    allowed_exts=_image_exts)

    task_id = uuid.uuid4().hex[:12]
    start = time.time()

    try:
        ocr_engine = OCREngine()
        loop = asyncio.get_running_loop()

        # 选择识别方式
        if segmentation:
            ocr_results = await loop.run_in_executor(
                None, ocr_engine.recognize_image_with_segmentation, path,
            )
        else:
            ocr_results = await loop.run_in_executor(
                None, ocr_engine.recognize_image_file, path,
            )

        # 置信度提升
        full_text = await loop.run_in_executor(
            None, ocr_engine.get_full_text, ocr_results,
        )
        if boost_confidence:
            ocr_results = await loop.run_in_executor(
                None, ocr_engine.boost_confidence_with_context,
                ocr_results, full_text,
            )

        low_confidence = [r for r in ocr_results if r.get("confidence", 1.0) < 0.6]

        # 行业字段识别
        industry_fields = None
        if industry != "general":
            recognizer = IndustryFieldRecognizer(industry=industry)
            industry_fields = await loop.run_in_executor(
                None, recognizer.recognize_fields, ocr_results,
            )

        elapsed = time.time() - start

        # 存入数据库
        if db_manager:
            try:
                db_manager.create_task(
                    task_id=task_id,
                    word_file=image_file.filename,
                    pdf_file="",
                    user_id=key_info.key_id if key_info else "anonymous",
                )
                db_manager.update_task(task_id, status="completed",
                                        result_summary=f"OCR识别完成，{len(ocr_results)}项")
            except Exception as db_err:
                logger.warning(f"数据库写入失败: {db_err}")

        return ImageOCRResult(
            task_id=task_id,
            full_text=full_text,
            ocr_items_count=len(ocr_results),
            low_confidence_count=len(low_confidence),
            industry_fields=industry_fields,
            elapsed_seconds=round(elapsed, 2),
        )
    except Exception as e:
        logger.exception(f"图片 OCR 失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="图片 OCR 识别失败，请检查文件格式后重试。",
        )
    finally:
        background_tasks.add_task(_cleanup_temp_file, path)


# ============================================================
# LLM 供应商管理接口
# ============================================================

@app.get(
    "/api/v1/llm/providers",
    response_model=list[LLMProviderStatus],
    tags=["配置"],
    summary="列出 LLM 供应商状态",
    description="列出所有已配置的 LLM 供应商及其可用状态。",
)
async def list_llm_providers(
    key_info = Depends(require_auth()),
):
    providers = []
    try:
        engine = LLMEngine()
        available = engine.list_available_providers()
        for p in available:
            providers.append(LLMProviderStatus(
                provider=p["provider"],
                model=p["model"],
                available=p["available"],
                message=p.get("message"),
            ))
    except Exception as e:
        logger.warning(f"获取 LLM 供应商状态失败: {e}")
    return providers


@app.post(
    "/api/v1/llm/test",
    response_model=LLMTestResult,
    tags=["配置"],
    summary="测试 LLM 连通性",
    description="测试指定 LLM 供应商的连通性，发送简单 prompt 验证服务可用。",
)
async def test_llm_connection(
    config: LLMProviderConfig,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_PROFILES)),
):
    try:
        engine = LLMEngine(provider=config.provider)
        if config.model:
            engine.set_provider(config.provider, model=config.model,
                                 api_key=config.api_key,
                                 base_url=config.base_url,
                                 timeout=config.timeout)
        available = engine.is_available()
        if not available:
            return LLMTestResult(
                provider=config.provider,
                model=config.model or "default",
                connected=False,
                error="供应商不可用，请检查配置和服务状态",
            )

        # 发送简单测试 prompt
        response = engine.generate_text("请回复：连通测试成功", max_tokens=20)
        return LLMTestResult(
            provider=config.provider,
            model=config.model or "default",
            connected=True,
            response_preview=response[:100] if response else None,
        )
    except Exception as e:
        return LLMTestResult(
            provider=config.provider,
            model=config.model or "default",
            connected=False,
            error=str(e)[:200],
        )


@app.put(
    "/api/v1/llm/default",
    tags=["配置"],
    summary="设置默认 LLM 供应商",
    description="设置默认的 LLM 供应商和模型配置。",
)
async def set_default_llm_provider(
    config: LLMProviderConfig,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_PROFILES)),
):
    from config import LLM_CONFIG
    LLM_CONFIG["default_provider"] = config.provider
    if config.model:
        if config.provider in LLM_CONFIG:
            LLM_CONFIG[config.provider]["model"] = config.model
    if config.api_key and config.provider == "claude":
        LLM_CONFIG["claude"]["api_key"] = config.api_key
    if config.base_url and config.provider == "ollama":
        LLM_CONFIG["ollama"]["base_url"] = config.base_url

    return {
        "message": f"默认 LLM 供应商已设置为: {config.provider}",
        "provider": config.provider,
        "model": config.model,
    }


# ============================================================
# 数据库管理接口
# ============================================================

@app.get(
    "/api/v1/tasks",
    response_model=TaskListResponse,
    tags=["系统"],
    summary="查询历史任务列表",
    description="从数据库查询历史比对任务列表（支持分页）。",
)
async def list_tasks(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    key_info = Depends(require_auth()),
):
    if db_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库模块未启用。",
        )
    user_id = key_info.key_id if key_info else None
    tasks = db_manager.list_tasks(limit=limit, offset=offset, user_id=user_id)
    return TaskListResponse(
        total=len(tasks),
        tasks=[TaskListOut(
            task_id=t.get("task_id", ""),
            status=t.get("status", ""),
            created_at=t.get("created_at", ""),
            completed_at=t.get("completed_at"),
            result_summary=t.get("result_summary"),
        ) for t in tasks],
    )


@app.delete(
    "/api/v1/tasks/{task_id}",
    tags=["系统"],
    summary="删除历史任务",
    description="删除指定的历史比对任务记录。",
)
async def delete_task(
    task_id: str,
    key_info = Depends(require_auth()),
):
    if db_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库模块未启用。",
        )
    deleted = db_manager.delete_task(task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务不存在: {task_id}",
        )
    return {"message": f"任务 '{task_id}' 已删除", "task_id": task_id}


@app.post(
    "/api/v1/cleanup",
    response_model=CleanupResult,
    tags=["系统"],
    summary="清理过期数据",
    description="清理过期的比对任务和审计日志数据，确保非定制化场景下不留操作痕迹。",
)
async def cleanup_data(
    request: CleanupRequest,
    key_info = Depends(require_auth()),
    _ = Depends(require_permission(PERMISSION_MANAGE_KEYS)),
):
    if db_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库模块未启用。",
        )

    tasks_deleted = db_manager.cleanup_expired_tasks(
        max_age_hours=request.max_age_hours)
    audit_deleted = 0
    if request.cleanup_audit_logs:
        audit_deleted = db_manager.cleanup_expired_audit_logs(
            max_age_days=request.audit_max_age_days)

    return CleanupResult(
        tasks_deleted=tasks_deleted,
        audit_logs_deleted=audit_deleted,
        message=f"已清理 {tasks_deleted} 个过期任务" +
                (f"，{audit_deleted} 条审计日志" if request.cleanup_audit_logs else ""),
    )


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )