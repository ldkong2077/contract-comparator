# Contract Document Comparator / 合同扫描件比对工具

<p align="center">
  <strong>智能合同比对引擎 — 字段级 OCR 比对 · Excel 差异分析 · LLM 语义评估</strong>
  <br>
  <em>Intelligent Contract Comparison Engine — Field-Level OCR Diff, Excel Delta Analysis, LLM Semantic Evaluation</em>
</p>

> **⚠️ 重要免责声明 / Important Disclaimers**
>
> 1. **非法律意见**：本工具用于辅助人工复核，输出结果不构成法律意见或专业审计结论。
> 2. **需人工复核**：OCR 与 LLM 结果可能出错，正式签署、付款或审计前必须经人工确认。
> 3. **数据安全**：默认所有处理在本地完成；启用云端 LLM（Claude API）前，请确认组织的数据合规要求。
> 4. **第三方许可**：商业闭源使用前请自行审查 PyMuPDF（AGPL）、fpdf2（LGPL-3.0）、OpenCV wheel 等第三方许可。
>
> *This tool is for manual review only. Output does not constitute legal advice.
> OCR and LLM results may contain errors. Manual verification is required before
> signing, payment, or audit. All processing is local by default; review your
> organization's data compliance policy before enabling cloud LLM.*

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/OCR-RapidOCR%20%7C%20EasyOCR%20%7C%20Tesseract-orange" alt="Multi-OCR">
  <img src="https://img.shields.io/badge/LLM-Ollama%20%7C%20Claude-blueviolet" alt="Multi-LLM">
  <img src="https://img.shields.io/badge/UI-CLI%20%7C%20Streamlit%20%7C%20REST%20API-red" alt="Multi-UI">
  <br>
  <img src="https://img.shields.io/badge/Status-Beta%20%2F%20Pilot-yellow" alt="Status: Beta / Pilot">
  <img src="https://img.shields.io/badge/DB-SQLite%20%7C%20WAL%20%7C%20Encrypted-yellow" alt="Database">
</p>

---

## 📋 Table of Contents / 目录

- [Overview / 项目概览](#overview--项目概览)
- [Key Features / 核心功能](#key-features--核心功能)
- [Architecture / 系统架构](#architecture--系统架构)
- [Quick Start / 快速开始](#quick-start--快速开始)
- [Usage / 使用指南](#usage--使用指南)
- [API Reference / API 参考](#api-reference--api-参考)
- [Deployment / 部署方案](#deployment--部署方案)
- [Security / 安全体系](#security--安全体系)
- [Configuration / 配置说明](#configuration--配置说明)
- [Project Structure / 项目结构](#project-structure--项目结构)
- [Roadmap / 路线图](#roadmap--路线图)
- [Contributing / 贡献指南](#contributing--贡献指南)
- [License / 许可协议](#license--许可协议)

---

## Screenshots / 功能展示

<p align="center">
  <em>Screenshots are available in the <a href="docs/images/">docs/images/</a> directory.</em>
  <br>
  <em>功能截图请参阅 <a href="docs/images/">docs/images/</a> 目录。</em>
</p>

---

## Overview / 项目概览

### 🇨🇳 中文

**合同扫描件比对工具** v4.0.0 是一款面向法务、财务、审计等专业领域的文档智能比对系统。核心解决**盖章合同扫描件（PDF/图片）与原始 Word/Excel 文档之间的内容差异检测**问题。

> **一句话:** 把纸质合同扫描进去，自动告诉你哪里被改了。

通过 OCR 识别、字段级智能抽取、多维比对引擎和 LLM 语义分析，实现对合同金额、日期、条款等关键要素的自动化核对，大幅降低人工复核成本。

### 🇬🇧 English

**Contract Document Comparator** v4.0.0 is a professional document intelligence comparison system tailored for legal, financial, and audit domains. Its core mission is to **detect content differences between signed/scanned contracts (PDF/images) and original Word/Excel documents**.

> **In a nutshell:** Scan a paper contract, get an automatic diff report telling you exactly what changed.

It combines OCR recognition, field-level intelligent extraction, multi-dimensional comparison engines, and LLM-powered semantic analysis to automate key element verification — slashing manual review costs.

---

## Key Features / 核心功能

### 🔍 Field-Level OCR Comparison / 字段级 OCR 比对

| Feature | Description |
|---------|-------------|
| **Multi-Engine OCR** | RapidOCR (PP-OCRv5, default) → EasyOCR → Tesseract, auto-fallback |
| **Image Preprocessing** | OpenCV: adaptive binarization (Otsu + Sauvola), deskewing, denoising, quality assessment |
| **Intelligent Field Extraction** | Regex-based extraction for amounts, dates, numbers, contract IDs, party names. Full-width/half-width normalization, Chinese uppercase amount parsing |
| **Low-Confidence Marking** | Fields below configurable confidence threshold are flagged for manual review |

### 📊 Excel Comparison / Excel 差异分析

| Feature | Description |
|---------|-------------|
| **Cell-Level Diff** | Direct cell value comparison with smart header matching |
| **Row Insertion/Deletion Detection** | Identifies added/removed rows via hash-based fingerprinting |
| **Multi-Sheet Support** | Compares all sheets in a workbook |

### 🔄 Full-Text Diff / 全文差异追踪

| Feature | Description |
|---------|-------------|
| **diff-match-patch Engine** | Google's battle-tested diff algorithm |
| **Risk Classification** | High / Medium / Low risk levels for each diff chunk |
| **Context-Aware Comparison** | Understands document structure, not just raw text |

### 🤖 LLM-Powered Analysis / LLM 语义分析

| Feature | Description |
|---------|-------------|
| **Dual Provider** | Ollama (local, e.g., qwen3.5-0.8b) + Claude API (claude-sonnet-4-20250514) |
| **Semantic Evaluation** | LLM judges whether differences are substantive vs. formatting-only |
| **Fallback Chain** | LLM unavailable → auto-degrade to rule-based comparison |

### 🖥️ Three UI Options / 三合一交互界面

| UI | Description | Port |
|----|-------------|------|
| **CLI** | Command-line interface via `argparse` | — |
| **Streamlit Web** | Rich web dashboard with visual diff | `:8501` |
| **FastAPI REST** | Local/Private REST API with Swagger docs | `:8080` |

### 📦 Multi-Format Export / 多格式导出

TXT · JSON · DOCX (redline) · XLSX (multi-sheet) · PDF (A4, reportlab) · ZIP bundle

### 🏭 Industry Presets / 行业预设

Built-in presets for: **General** · **Construction** · **Leasing** · **Procurement** · **Labor**

---

## Architecture / 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   CLI    │  │  Streamlit   │  │  FastAPI REST    │   │
│  │ (main.py)│  │(app_streamlit│  │ (api_server.py)  │   │
│  └────┬─────┘  └──────┬───────┘  └────────┬─────────┘   │
├───────┴───────────────┴────────────────────┴─────────────┤
│                    Core Pipeline                          │
│  ┌──────────┐  ┌────────────┐  ┌──────────┐            │
│  │   PDF    │  │  Field     │  │Compare   │            │
│  │Processor │─▶│ Extractor  │─▶│ Engine   │            │
│  │(fitz)    │  │ (regex)    │  │(matcher) │            │
│  └──────────┘  └────────────┘  └────┬─────┘            │
│  ┌──────────┐  ┌────────────┐       │                   │
│  │   OCR    │  │  Word/Excel│       │                   │
│  │ Engine   │  │  Parser    │       │                   │
│  │(RapidOCR)│  │(docx/xlsx) │       │                   │
│  └──────────┘  └────────────┘       │                   │
│  ┌──────────┐  ┌────────────┐       │                   │
│  │  Full-   │  │    LLM     │       │                   │
│  │Text Diff │  │  Analyser  │       │                   │
│  └──────────┘  └────────────┘       │                   │
│  ┌──────────┐  ┌────────────┐       │                   │
│  │  Report  │◀─│  Exporter  │◀──────┘                   │
│  │ Generator│  │(TXT/JSON/  │                           │
│  │          │  │ DOCX/XLSX/ │                           │
│  │          │  │ PDF/ZIP)   │                           │
│  └──────────┘  └────────────┘                           │
├─────────────────────────────────────────────────────────┤
│                    Infrastructure                         │
│  ┌──────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ Security │  │  Database  │  │  Error Handler   │    │
│  │(auth/    │  │  (SQLite   │  │  (Structured     │    │
│  │  RBAC/   │  │   WAL/     │  │   Logger /       │    │
│  │  Rate    │  │   Encrypt) │  │   Audit Trail)   │    │
│  │  Limit)  │  │            │  │                  │    │
│  └──────────┘  └────────────┘  └──────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### Component Highlights / 组件要点

- **OCR Engine** (`ocr_engine.py`, ~1800 lines): Multi-engine orchestration with image preprocessing pipeline, confidence scoring, and automatic fallback
- **Field Extractor** (`field_extractor.py`, ~1000 lines): Regex-based extraction with 15+ pattern types, Chinese financial amount normalization, date unification
- **Comparison Engine** (`comparator.py`): Field-level matching with context-aware strategies — number tolerance, keyword overlap, structural alignment
- **Full-Text Diff** (`full_text_diff.py`): Google diff-match-patch with risk classification (high/medium/low)
- **Excel Comparator** (`excel_comparator.py`, ~1300 lines): Cell-level comparison, row insertion/deletion detection, multi-sheet support
- **Report Exporter** (`report_exporter.py`, ~1000 lines): 6 export formats (TXT, JSON, DOCX redline, XLSX, PDF, ZIP)
- **Security Layer** (`security.py`, ~870 lines): File upload validation, sensitive data masking, input sanitization, audit logging
- **Auth & RBAC** (`auth.py`, ~350 lines): API key HMAC-SHA256 authentication, role-based access (Admin/Analyst/Viewer), rate limiting
- **Database** (`database.py`, ~1000 lines): SQLite with WAL mode, Fernet encryption for sensitive fields, auto-cleanup, full CRUD
- **Error Handler** (`error_handler.py`, ~890 lines): 6 custom exception types, structured logging, singleton audit trail, graceful degradation decorators
- **LLM Engine** (`llm_engine.py`): Dual-provider (Ollama + Claude) with prompt templates for field extraction and semantic analysis
- **API Server** (`api_server.py`, ~1960 lines): FastAPI with 20+ endpoints, middleware, authentication, TaskStore, ProfileStore
- **Streamlit UI** (`app_streamlit.py`, ~2350 lines): Rich web dashboard with real-time comparison visualization

---

> **ℹ️ 开源版本声明 / Open-Source Version Notice**
>
> 本开源版本仅供本地 / 内网试用与评估，不承诺企业级 SLA、安全合规保证或商业技术支持。
> 如需生产环境部署、私有化定制或企业 SLA 支持，请联系项目维护团队获取商业版本信息。
>
> *This open-source version is intended for local/intranet evaluation only.*
> *No enterprise SLA, compliance guarantees, or commercial support is provided.*
> *For production deployment, private customization, or enterprise SLA support, please contact the project maintainers.*

---

## 商业版本 / Commercial Version

本开源版本功能完整，可满足个人和小型团队的合同比对需求。商业版本在此基础上提供企业级增强功能：

### 功能对比 / Feature Comparison

| 功能 | 开源版 | 商业版 |
|------|:------:|:------:|
| **核心比对** | | |
| 文件对比 (Word vs PDF) | ✅ | ✅ |
| 字段级 OCR 比对 | ✅ | ✅ |
| 全文差异追踪 | ✅ | ✅ |
| Excel 表格对比 | ✅ | ✅ |
| **OCR 引擎** | | |
| Tesseract / RapidOCR / EasyOCR | ✅ | ✅ |
| 商业 OCR API (阿里云/腾讯云) | ❌ | ✅ |
| 批量 OCR 处理 | ❌ | ✅ |
| **LLM 分析** | | |
| Ollama 本地推理 | ✅ | ✅ |
| Claude / GPT-4 云端分析 | ✅ | ✅ |
| 自定义 Prompt 模板 | ❌ | ✅ |
| **导出格式** | | |
| TXT / JSON | ✅ | ✅ |
| Word 红线标注 | ✅ | ✅ |
| Excel 多 Sheet | ✅ | ✅ |
| PDF A4 报告 | ✅ | ✅ |
| 定制化报告模板 | ❌ | ✅ |
| **用户管理** | | |
| API Key 认证 | ✅ | ✅ |
| RBAC 权限控制 | ✅ | ✅ |
| SSO / LDAP 集成 | ❌ | ✅ |
| **审计与合规** | | |
| 操作审计日志 | ✅ | ✅ |
| 数据脱敏 | ✅ | ✅ |
| 等保合规支持 | ❌ | ✅ |
| **部署与支持** | | |
| Docker 单机部署 | ✅ | ✅ |
| Kubernetes 集群部署 | ❌ | ✅ |
| 高可用架构 | ❌ | ✅ |
| 7x24 技术支持 | ❌ | ✅ |
| 私有化定制开发 | ❌ | ✅ |

### 联系我们 / Contact Us

| 渠道 | 联系方式 | 用途 |
|------|----------|------|
| **综合咨询** | info@numboxhub.com | 商业版本购买、定制开发、技术支持 |
| **安全报告** | info@numboxhub.com | 安全漏洞报告 |
| **GitHub Issues** | [Issues](https://github.com/ldkong2077/contract-comparator/issues) | 功能建议、Bug 报告 |

> **提示**: 开源版本用户可通过上述邮箱联系我们获取商业版本试用授权或技术咨询。

---

## Quick Start / 快速开始

### Prerequisites / 前置条件

- Python 3.10+
- pip
- (Optional) [Ollama](https://ollama.ai/) for local LLM inference
- (Optional) [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for fallback OCR engine

### Installation / 安装

```bash
# Clone repository
git clone https://github.com/ldkong2077/contract-comparator.git
cd contract-comparator

# Install dependencies AND the package itself (REQUIRED: 否则 `python -m contract_comparator ...` 会报 ModuleNotFoundError)
pip install -r requirements.lock
pip install -e .

# (Optional) For development, include dev/test extras
pip install -e ".[dev]"
```

> **Note:** First run will download RapidOCR model files (~50MB). Ensure internet connectivity.

### Basic Usage / 基础使用

```bash
# Compare a Word document against a scanned PDF
python -m contract_comparator.cli.main compare --word 原版合同.docx --pdf 扫描件.pdf

# Specify output directory
python -m contract_comparator.cli.main compare --word 原版合同.docx --pdf 扫描件.pdf --output ./results

# Enable LLM-assisted extraction (requires local Ollama)
python -m contract_comparator.cli.main compare --word 原版合同.docx --pdf 扫描件.pdf --use-llm

# Specify Ollama model
python -m contract_comparator.cli.main compare --word 原版合同.docx --pdf 扫描件.pdf --use-llm --model qwen3.5-0.8b
```

### Docker Deployment / Docker 部署

```bash
# Start core services (Streamlit + FastAPI). Ollama 是可选 LLM 服务，默认不随 up -d 启动
docker-compose up -d
# 如需启用本地 LLM，需加 --profile llm：
# docker-compose --profile llm up -d

# Access:
#   Streamlit UI: http://localhost:8501
#   FastAPI Docs: http://localhost:8080/docs
```

---

## Usage / 使用指南

### CLI Mode / 命令行模式

```bash
# Document comparison with full options
python -m contract_comparator.cli.main compare \
    --word 原版合同.docx \
    --pdf 扫描件.pdf \
    --output ./results \
    --profile construction \
    --use-llm \
    --model qwen3.5-0.8b \
    --export-format json \
    --verbose

# Excel comparison
python -m contract_comparator.cli.main excel \
    --file-a old.xlsx \
    --file-b new.xlsx \
    --output ./diff

# OCR text extraction
python -m contract_comparator.cli.main ocr \
    --input scan.pdf \
    --output ./ocr_result
```

### Streamlit Web UI

```bash
streamlit run src/contract_comparator/web/app_streamlit.py
# Opens at http://localhost:8501
```

Features: File upload, side-by-side diff visualization, preset profile selection, export to all formats.

### FastAPI REST Server

```bash
uvicorn contract_comparator.api.api_server:app --host 0.0.0.0 --port 8080 --reload
# API docs: http://localhost:8080/docs
```

### Export Formats / 导出格式

| Format | Description | Command Flag |
|--------|-------------|--------------|
| TXT | Plain text report | `--export-format txt` |
| JSON | Structured data | `--export-format json` |
| DOCX | Redline Word document | `--export-format docx` |
| XLSX | Multi-sheet Excel workbook | `--export-format xlsx` |
| PDF | A4 formatted report | `--export-format pdf` |
| ZIP | Bundle of all formats | `--export-format zip` |

---

## API Reference / API 参考

### Endpoints (FastAPI: `/api/v1/`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/compare` | Execute document comparison |
| GET | `/api/v1/compare/{task_id}` | Get comparison result |
| GET | `/api/v1/compare/{task_id}/status` | Poll task status |
| POST | `/api/v1/compare/batch` | Batch comparison |
| DELETE | `/api/v1/compare/{task_id}` | Delete task result |
| GET | `/api/v1/export/{task_id}` | Export result in specified format |
| GET | `/api/v1/profiles` | List industry presets |
| POST | `/api/v1/profiles` | Create custom profile |
| GET | `/api/v1/profiles/{name}` | Get profile details |
| PUT | `/api/v1/profiles/{name}` | Update profile |
| DELETE | `/api/v1/profiles/{name}` | Delete profile |
| POST | `/api/v1/auth/key` | Generate API key |
| POST | `/api/v1/auth/verify` | Verify API key |
| GET | `/api/v1/auth/keys` | List API keys (Admin) |
| DELETE | `/api/v1/auth/key/{key_id}` | Revoke API key (Admin) |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/metrics` | System metrics (Admin) |

### Authentication

API Key-based authentication. Include header:
```
X-API-Key: your-api-key-here
```

### Rate Limiting

- Default: 60 requests/minute per key
- Admin: 300 requests/minute
- Configurable via `config/api_keys.json`

---

## Deployment / 部署方案

### Docker Compose (Recommended)

```yaml
# docker-compose.yml includes:
#   - contract-api (FastAPI :8080)
#   - contract-ui (Streamlit :8501)
#   - ollama (Optional LLM :11434)
```

```bash
docker-compose up -d
```

### Manual Deployment

```bash
# Local REST API server
uvicorn contract_comparator.api.api_server:app --host 0.0.0.0 --port 8080 --workers 4

# Streamlit UI
streamlit run src/contract_comparator/web/app_streamlit.py --server.port 8501 --server.address 0.0.0.0
```

### Docker Image

```bash
docker build -t contract-comparator .
# 注意：默认 CMD 启动的是 Streamlit Web UI（端口 8501）
docker run -p 8501:8501 contract-comparator
# 如需运行 REST API（覆盖默认 CMD），映射 8080：
docker run -p 8080:8080 contract-comparator \
  uvicorn contract_comparator.api.api_server:app --host 0.0.0.0 --port 8080
```

---

## Security / 安全体系

| Category | Measure |
|----------|---------|
| **File Upload** | Magic byte validation, extension whitelist, file size limit (50MB) |
| **API Keys** | HMAC-SHA256 signed, Fernet encrypted at rest, configurable expiration |
| **RBAC** | 3 roles: Admin (full access), Analyst (compare + export), Viewer (export only — **无 compare 权限**，仅可导出/下载已有结果) |
| **Rate Limiting** | Per-key rate limiting with configurable thresholds |
| **Input Sanitization** | Strips XSS, SQL injection, command injection patterns |
| **Sensitive Data** | Masker for 5 types: ID numbers, phone, bank cards, API keys, passwords |
| **Audit Trail** | Singleton audit logger with tamper-evident hashing |
| **Encryption** | Fernet symmetric encryption for sensitive config fields, CBC mode |
| **Temp Files** | SecureTempFileManager with auto-cleanup, `tempfile.mkstemp` |

---

## Configuration / 配置说明

### `config.py` — Core Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OCR_ENGINE` | `rapidocr` | Primary OCR engine |
| `OCR_CONFIDENCE_THRESHOLD` | `0.7` | Minimum confidence for auto-accept |
| `LLM_PROVIDER` | `ollama` | `ollama` or `claude` |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload size (MB) |
| `DATABASE_URL` | `sqlite:///data/comparisons.db` | Database connection |
| `RATE_LIMIT_RPM` | `30` | Requests per minute per key (实际变量名见 `config.py`) |

### `config/api_keys.json` — API Key Storage

```json
{
  "keys": [],
  "created_at": "",
  "updated_at": ""
}
```

> Keys are generated via `POST /auth/key` at runtime. See `config/api_keys.json.template` for the empty schema.

### Environment Variables (`.env.example`)

| Variable | Description |
|----------|-------------|
| `CLAUDE_API_KEY` | Claude API key for LLM features |
| `OLLAMA_BASE_URL` | Ollama server URL (default: `http://localhost:11434`) |
| `ENCRYPTION_KEY` | Fernet encryption key for sensitive data |
| `LOG_LEVEL` | Logging level (default: `INFO`) |

---

## Project Structure / 项目结构

```
contract-comparator/
├── .github/                        # GitHub community files
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.md
│   │   └── feature_request.md
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── CODE_OF_CONDUCT.md
├── .dockerignore
├── .env.example
├── .gitignore
├── CHANGELOG.md                    # Release history (Keep a Changelog)
├── CONTRIBUTING.md                 # Contribution guidelines
├── Dockerfile                      # Multi-stage Docker image
├── LICENSE                         # MIT License
├── README.md                       # This file
├── SECURITY.md                     # Security policy
├── THIRD_PARTY_LICENSES.md         # Third-party license analysis
├── docker-compose.yml              # Multi-service Docker orchestration
├── pyproject.toml                  # Project metadata & build config
├── requirements.lock               # Locked dependencies (reproducible build)
├── requirements.txt                # Loose dependencies (development reference)
├── config/
│   └── api_keys.json.template      # API key config template
├── docs/                           # Documentation
│   ├── architecture.md             # System architecture with Mermaid diagrams
│   ├── installation.md             # Installation guide (pip/Docker)
│   ├── usage.md                    # CLI/Streamlit/FastAPI usage
│   ├── api-reference.md            # REST API reference
│   ├── deployment-guide.md         # Production deployment
│   ├── operations-guide.md         # Operations manual
│   ├── security-baseline.md        # Security baseline
│   ├── testing-guide.md            # Testing guide
│   └── images/                     # Screenshots and diagrams
├── examples/                       # Usage examples
│   ├── api/                        # API call examples (curl, Python)
│   └── profiles/                   # Custom profile templates
├── src/
│   └── contract_comparator/        # Main package
│       ├── __init__.py             # Package init, public API exports
│       ├── config.py               # Global configuration (~300 lines)
│       ├── database.py             # SQLite database layer (~1000 lines)
│       ├── error_handler.py        # Error handling & structured logging (~890 lines)
│       ├── profiles.py             # Industry presets manager
│       ├── security.py             # Security layer (~870 lines)
│       ├── utils.py                # Shared utilities
│       ├── api/                    # FastAPI REST API
│       │   ├── __init__.py
│       │   └── api_server.py       # REST endpoints (~1960 lines)
│       ├── cli/                    # CLI entry point
│       │   ├── __init__.py
│       │   └── main.py             # argparse CLI (~450 lines)
│       ├── compare/                # Comparison engines
│       │   ├── __init__.py
│       │   ├── comparator.py       # Field-level comparison
│       │   ├── excel_comparator.py # Excel diff engine (~1300 lines)
│       │   ├── field_extractor.py  # Intelligent field extraction (~1000 lines)
│       │   └── full_text_diff.py   # diff-match-patch implementation
│       ├── engine/                 # Core processing engines
│       │   ├── __init__.py
│       │   ├── pdf_processor.py    # PDF to image conversion
│       │   ├── word_parser.py      # Word document parser
│       │   └── ocr/                # Multi-engine OCR subsystem
│       │       ├── __init__.py
│       │       ├── engine.py       # OCR engine orchestration (~1800 lines)
│       │       ├── preprocessor.py # Image preprocessing (OpenCV)
│       │       ├── binarize.py     # Adaptive binarization (Otsu/Sauvola)
│       │       ├── dewarp.py       # Document dewarping
│       │       ├── layout.py       # Layout analysis
│       │       ├── quality.py      # Image quality assessment
│       │       ├── fallback.py     # Engine auto-fallback
│       │       ├── postcorrector.py# Post-OCR correction
│       │       ├── industry.py     # Industry-specific OCR configs
│       │       └── logger.py       # OCR logging
│       ├── export/                 # Report export modules
│       │   ├── __init__.py
│       │   ├── report_exporter.py  # Multi-format export (~1000 lines)
│       │   └── report_generator.py # Legacy text report generator
│       ├── llm/                    # LLM integration
│       │   ├── __init__.py
│       │   └── llm_engine.py       # Dual-provider (Ollama + Claude)
│       └── web/                    # Web UI
│           ├── __init__.py
│           └── app_streamlit.py    # Streamlit dashboard (~2350 lines)
└── tests/                          # Test suite (~5400 lines, 22 files)
    ├── conftest.py                 # Pytest fixtures
    └── test_*.py                   # Unit & integration tests
```

---

## Roadmap / 路线图

### v4.x — Current Beta / Pilot

- ✅ Multi-engine OCR with auto-fallback
- ✅ Field-level and full-text comparison
- ✅ Excel comparison with row insertion/deletion detection
- ✅ 6 export formats (TXT, JSON, DOCX, XLSX, PDF, ZIP)
- ✅ Three UI options: CLI, Streamlit, FastAPI REST
- ✅ RBAC authentication with rate limiting
- ✅ LLM integration (Ollama + Claude)
- ✅ Docker deployment
- ✅ Industry presets (construction, leasing, procurement, labor)

### v4.1 — Short Term (Q3 2026)

- ⬜ Image comparison via Streamlit upload
- ⬜ Comparison history browser
- ⬜ Email notification for batch completion
- ⬜ i18n support (English / Japanese / Korean)
- ⬜ More export styling options

### v4.2 — Medium Term (Q4 2026)

- ⬜ Plugin system for custom extractors
- ⬜ Table structure comparison
- ⬜ Batch OCR optimization with GPU acceleration
- ⬜ Webhook integration for CI/CD pipelines
- ⬜ Performance dashboard

### v5.0 — Long Term

- ⬜ Native desktop client (Tauri)
- ⬜ Real-time collaborative review
- ⬜ AI-powered contract clause suggestion
- ⬜ Cloud storage integration (OSS / S3)
- ⬜ Enterprise SSO (LDAP / OAuth2)

---

## Contributing / 贡献指南

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

**Quick start for contributors:**

```bash
# Setup dev environment
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src/contract_comparator

# Code style
pylint src/contract_comparator/
```

See [CHANGELOG.md](CHANGELOG.md) for release history.

---

## License / 许可协议

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

### Third-Party License Notice

This project depends on third-party libraries with varying licenses:

| Dependency | License | Commercial Note |
|------------|---------|-----------------|
| **PyMuPDF** | **AGPL** | Closed-source commercial use requires a commercial license from Artifex or replacement of this component. Open-source use under AGPL is acceptable. |
| **fpdf2** | **LGPL-3.0-only** | Retain license notice; distribution of modified binaries requires source disclosure. |
| **opencv-python-headless** | Apache-2.0 + third-party binary licenses | Review bundled FFmpeg/etc. licenses for commercial distribution. |

See [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) for the complete dependency license matrix.

---

## Acknowledgments / 致谢

- [RapidOCR](https://github.com/RapidAI/RapidOCR) — PP-OCRv5 inference engine
- [diff-match-patch](https://github.com/google/diff-match-patch) — Google's diff algorithm
- [ReportLab](https://www.reportlab.com/) — PDF generation
- [FastAPI](https://fastapi.tiangolo.com/) — REST framework
- [Streamlit](https://streamlit.io/) — Web UI framework
- All contributors and users of this project

---

<p align="center">
  <sub>Built with ❤️ for the legal, financial, and audit communities</sub>
  <br>
  <sub>为法务、财务、审计社区精心打造</sub>
</p>
