# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] - 2026-05-25

### Added
- Complete 7-step comparison pipeline: Word parse → PDF render → OCR → field extraction → field comparison → full-text diff → LLM analysis
- RapidOCR (PP-OCRv5) with ONNXRuntime as primary OCR engine
- Multi-engine fallback: RapidOCR → EasyOCR → Tesseract
- Adaptive image preprocessing (Otsu/Sauvola binarization, dewarping, quality assessment)
- Chinese financial amount extraction (uppercase/lowercase numbers, keyword-aware)
- Comprehensive date normalization (ISO 8601)
- Field-level comparison engine with tolerance matching
- Full-text diff using diff-match-patch algorithm with risk classification
- LLM semantic analysis (Ollama local + Claude API dual provider)
- Three UI interfaces: CLI (argparse), Streamlit web UI, FastAPI REST API (20+ endpoints)
- Export formats: TXT, JSON, DOCX (redline), XLSX (multi-sheet), PDF (reportlab), ZIP bundle
- SQLite database for task persistence with auto-cleanup (WAL mode, Fernet encrypted)
- API Key authentication with HMAC-SHA256 + RBAC (Admin/Analyst/Viewer)
- Rate limiting (token bucket: burst + per-minute)
- File upload validation (magic bytes, size check, integrity check)
- Sensitive data masking (phones, emails, ID cards, bank accounts, company seals)
- Audit logging with rotation (JSON Lines, 10MB, 5 backups)
- Secure temp file management (icacls/chmod 700)
- 5 industry presets: general, construction, leasing, procurement, labor
- Excel comparison engine with smart column/row matching
- Docker deployment with docker-compose (Streamlit:8501 + FastAPI:8080 + Ollama:11434)
- MIT License

### Security
- **CRITICAL**: Fixed API Key logged in plaintext — now masked as `abc...xyz` in logs, full key only printed to stdout
- **CRITICAL**: Removed Query parameter authentication path — API Key now accepted exclusively via `X-API-Key` header
- Fixed Dockerfile version label (v3.0.0 → v4.0.0)

### Changed
- Refactored monolithic `ocr_engine.py` (1828 lines) into 11-module `ocr/` package with backward-compatible shim
- Added `--no-boost-ocr` argument wiring in CLI (`main.py` L417)
- `IMAGE_CONFIG.max_image_size_mb` check now enforced in image preprocessing pipeline
- Fixed `ImagePreprocessor.deskew_image` unbound variable bug (NameError when no rotation needed)
- Removed unused `get_env_bool/get_env_int/get_env_float` helpers from `config.py`
- Consolidated 3 scattered `import re` statements to module top in `ocr_engine.py`

### Added (Infrastructure)
- `.github/dependabot.yml` — Weekly automated dependency updates (pip + GitHub Actions)
- CodeQL security analysis job in CI workflow
- `.env.example` — Added `ENCRYPTION_KEY` generation command
- `scripts/backup_db.sh` — SQLite online backup script with retention policy
- `examples/` directory with config template and API usage examples

### Documentation
- README: Added dynamic badges (GitHub Stars, CI, Docker Pulls, Codecov)
- README: Added screenshots section with placeholder images
- README: Full bilingual (Chinese/English) documentation
- docs/: Architecture, installation, usage, and API reference documents
