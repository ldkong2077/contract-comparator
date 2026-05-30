# Testing Guide / 测试指南

## Overview / 概述

This document describes how to set up and run tests for the Contract Comparator project.

---

## 1. Prerequisites / 前置条件

- Python 3.11 or 3.12 (recommended)
- pip

---

## 2. Setup / 环境搭建

### 2.1 Create Virtual Environment

```bash
# From project root
python3.11 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### 2.2 Install Dependencies

```bash
# Install locked production dependencies
pip install -r requirements.lock

# Install dev/testing dependencies
pip install pytest pytest-cov coverage
```

### 2.3 Verify Setup

```bash
python -c "import pytest; print(f'pytest {pytest.__version__} ready')"
```

---

## 3. Running Tests / 运行测试

### 3.1 Run All Tests

```bash
pytest
```

### 3.2 Run with Coverage

```bash
pytest --cov=. --cov-report=term --cov-report=html
```

### 3.3 Run Specific Test Files

```bash
# Security tests
pytest tests/test_security.py -v

# Database tests
pytest tests/test_database.py -v

# Error handler tests
pytest tests/test_error_handler.py -v

# Comparison tests
pytest tests/test_comparator.py -v
```

### 3.4 Run Smoke Test

```bash
python tests/_test_security.py
```

---

## 4. Test Categories / 测试分类

### 4.1 Existing Unit Tests

| Test File | Lines | Coverage Target | Status |
|-----------|-------|-----------------|--------|
| `test_security.py` | 483 | File validation, masking, sanitization, audit logging | ✅ Comprehensive |
| `test_database.py` | 277 | SQLite CRUD, task management | ✅ Good |
| `test_error_handler.py` | 490 | Exception hierarchy, structured logging | ✅ Comprehensive |
| `test_comparator.py` | 212 | Field comparison | ✅ Good |
| `test_field_extractor.py` | 244 | Field extraction regex | ✅ Good |
| `test_llm_engine.py` | 244 | LLM provider switching | ✅ Good |
| `test_ocr_engine.py` | 237 | OCR results processing | ⚠️ No E2E |
| `test_full_text_diff.py` | 294 | Text diff engine | ✅ Good |
| `test_report_exporter.py` | 490 | JSON export | ✅ Good |
| `test_excel_comparator.py` | 377 | Excel comparison | ✅ Good |
| `test_config.py` | 220 | Configuration loading | ✅ Good |
| `test_api_security.py` | ~250 | API security regression tests | ✅ Written |

### 4.2 Required Security Regression Tests (Written)

The following tests have been implemented in `tests/test_api_security.py`:

| Test File | Lines | Coverage | Status |
|-----------|-------|----------|--------|
| `test_api_security.py` | ~250 | API Key masking, error response, magic validation, rate limiter, bootstrap key | ✅ Implemented |

**Test cases included:**

| # | Test | Description |
|---|------|-------------|
| 1 | `test_startup_does_not_print_plain_key` | Startup must not print full API Key to stdout |
| 2 | `test_500_response_has_no_exception_detail` | 500 errors return generic message with request_id |
| 3 | `test_exe_renamed_to_pdf_rejected` | Renamed .exe rejected even with .pdf extension |
| 4 | `test_rate_limiter_uses_role_and_key_id` | Rate limiter identifies client by role:key_id |
| 5 | `test_unknown_magic_with_strict_true_is_error` | Unknown magic bytes rejected in strict mode |
| 6 | `test_bootstrap_key_env_default_is_false` | ALLOW_BOOTSTRAP_ADMIN_KEY defaults to false |
| 7 | `test_upload_strict_magic_source_check` | API upload enforces strict_unknown_magic=True |
| 8 | `test_required_magic_numbers_present` | All required magic numbers (incl. BMP/TIFF/WebP) registered |

---

## 5. Test Requirements / 依赖说明

### 5.1 Dependencies

All tests require:
- `pytest>=7.4.0`
- `pytest-cov>=4.1.0`

Some tests (OCR, export) require the full dependency stack including:
- `rapidocr-onnxruntime`
- `opencv-python-headless`
- `PyMuPDF`

### 5.2 Known Limitations

| Limitation | Reason | Workaround |
|------------|--------|------------|
| No OCR E2E tests | Requires ~50MB model download | Smoke test with pre-downloaded model |
| No Streamlit UI tests | 2354-line single file | Wait for UI module split |
| No API integration tests | Requires FastAPI + running server | Use `httpx` + `TestClient` |
| No Docker build test | Requires Docker daemon | Manual build verification |

---

## 6. CI Configuration / CI 配置

Expected CI pipeline:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -r requirements.lock
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=. --cov-report=term
```
