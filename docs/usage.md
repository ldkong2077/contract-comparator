# Usage Guide / 使用指南

## CLI Mode / 命令行模式

### Basic Comparison

```bash
# Compare Word vs PDF
python main.py --word original.docx --pdf scanned.pdf

# Compare Word vs image
python main.py --word original.docx --pdf scanned.jpg

# Compare Word vs multiple images
python main.py --word original.docx --pdf page1.png --pdf page2.png
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `--word` | Path to original Word document | required |
| `--pdf` | Path to scanned PDF/image(s) | required |
| `--output` | Output directory | `./output` |
| `--profile` | Industry profile | `general` |
| `--use-llm` | Enable LLM assistance | `false` |
| `--model` | Ollama model name | `qwen3.5-0.8b` |
| `--export-format` | Export format (txt/json/docx/xlsx/pdf/zip) | `txt` |
| `--verbose` | Verbose output | `false` |

### Excel Comparison

```bash
python excel_comparator.py --old old.xlsx --new new.xlsx --output ./diff
```

### Examples

#### Construction Contract

```bash
python main.py \
    --word 施工合同.docx \
    --pdf 施工合同扫描件.pdf \
    --profile construction \
    --export-format pdf \
    --output ./reports
```

#### Batch with LLM

```bash
python main.py \
    --word 租赁合同.docx \
    --pdf 租赁合同.pdf \
    --use-llm \
    --model qwen3.5-0.8b \
    --export-format json \
    --verbose
```

## Streamlit Web UI / Streamlit 网页界面

### Start

```bash
streamlit run app_streamlit.py
```

Opens at `http://localhost:8501`.

### Features

- **File Upload:** Drag-and-drop Word, PDF, and image files
- **Profile Selection:** Choose from 5 industry presets
- **Side-by-Side Diff:** Visual comparison with highlighted differences
- **Risk Assessment:** Auto-classified high/medium/low risk items
- **Export:** Download results in any supported format
- **Comparison History:** Browse and re-open previous comparisons

### Screenshot

![Streamlit UI 主界面](../docs/images/streamlit_ui.png)

*图：Streamlit Web UI 主界面 — 支持文件上传、预设选择、实时对比可视化*

## FastAPI REST API / FastAPI REST 接口

### Start Server

```bash
# Development
uvicorn src.contract_comparator.api.api_server:app --host 0.0.0.0 --port 8080 --reload

# Production
uvicorn api_server:app --host 0.0.0.0 --port 8080 --workers 4
```

### Interactive Docs

Open `http://localhost:8080/docs` for Swagger UI.

### Authentication

All API endpoints (except `/health` and `/docs`) require authentication:

```bash
# Get an API key (requires admin)
curl -X POST "http://localhost:8080/api/v1/auth/key" \
  -H "X-API-Key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{"role": "Analyst", "expires_in_days": 30}'
```

### Example API Calls

#### Compare Documents

```bash
curl -X POST "http://localhost:8080/api/v1/compare" \
  -H "X-API-Key: your-api-key" \
  -F "word_file=@original.docx" \
  -F "pdf_file=@scanned.pdf" \
  -F "profile=general" \
  -F "use_llm=true"
```

#### Get Results

```bash
# Poll task status
curl "http://localhost:8080/api/v1/compare/{task_id}/status" \
  -H "X-API-Key: your-api-key"

# Get full result
curl "http://localhost:8080/api/v1/compare/{task_id}" \
  -H "X-API-Key: your-api-key"

# Export as PDF
curl "http://localhost:8080/api/v1/export/{task_id}?format=pdf" \
  -H "X-API-Key: your-api-key" \
  --output result.pdf
```

#### Health Check

```bash
curl "http://localhost:8080/api/v1/health"
```

### Rate Limiting

| Role | Default Limit |
|------|--------------|
| Viewer | 30 req/min |
| Analyst | 60 req/min |
| Admin | 300 req/min |

## Export Formats / 导出格式

### TXT

Plain text report with structured sections. Best for quick review.

### JSON

Structured data format with all fields and diff results. Ideal for programmatic processing.

### DOCX (Redline)

Microsoft Word document with track-changes-like formatting. Shows insertions (underlined, green) and deletions (strikethrough, red).

### XLSX

Multi-sheet Excel workbook:
- **Summary:** Overview of all differences
- **Fields:** Field-level comparison results
- **Details:** Full diff details
- **Confidence:** Low-confidence items requiring manual review

### PDF

A4-formatted report with professional layout using ReportLab. Includes header with comparison metadata, structured sections, and risk badges.

### ZIP

Bundle containing all available export formats in a single archive.

## Industry Presets / 行业预设

| Preset | Code | Suitable For |
|--------|------|--------------|
| General | `general` | Standard contract comparison |
| Construction | `construction` | Engineering contracts, BoQ items |
| Leasing | `leasing` | Lease/rental agreements |
| Procurement | `procurement` | Purchase orders, supply agreements |
| Labor | `labor` | Employment contracts |

Each preset customizes:
- Field extraction patterns (industry-specific terms)
- Comparison tolerance levels
- Risk classification thresholds
- Export formatting
