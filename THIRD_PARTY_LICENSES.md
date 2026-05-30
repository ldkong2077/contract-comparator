# Third Party Licenses / 第三方许可声明

This project uses third-party libraries with varying license terms. Below is the
complete list of direct dependencies and their licenses.

**Important:** This project itself is licensed under MIT (see [LICENSE](LICENSE)),
but users must comply with the license terms of each dependency when distributing
or deploying the software commercially.

---

## High-Risk Licenses (Requires Attention)

### PyMuPDF (fitz) — AGPL

| Field | Value |
|-------|-------|
| Used in | `pdf_processor.py` — PDF rendering and page-to-image conversion |
| License | **GNU Affero General Public License (AGPL)** |
| Source | https://pymupdf.io/ — Artifex Software |
| Risk | AGPL requires that if you distribute the software (including providing
it as a network service), you must make the complete source code available.
Closed-source commercial use requires a **commercial license** from Artifex. |
| Recommendation for open-source use | The AGPL obligations apply when PyMuPDF is
included. For GitHub open-source demo use, PyMuPDF under AGPL is acceptable as
the project is already open-source. |
| Recommendation for commercial use | Before closed-source commercial distribution,
either (1) purchase a commercial license from Artifex, (2) replace PyMuPDF with
an alternative whose license has been individually evaluated for the intended
use case, or (3) keep the entire project under AGPL. **License compatibility of
any alternative must be reviewed by legal counsel.** |

---

## Medium-Risk Licenses

### fpdf2 — LGPL-3.0-only

| Field | Value |
|-------|-------|
| Used in | `report_exporter.py` — PDF report generation |
| License | **LGPL-3.0-only** |
| Source | https://pypi.org/project/fpdf2/ |
| Obligation | If you modify fpdf2 itself and distribute the binary, you must
provide the modified source code. Static linking carries additional obligations.
Using fpdf2 as a standalone library via pip without modification generally does
not trigger source-code distribution requirements. |
| Recommendation | Retain this license notice in your documentation. If PDF export
is critical for commercial deployment, consider alternatives like `reportlab`
(BSD) or a commercial reporting library. |

### opencv-python-headless — Apache 2.0 + third-party binaries

| Field | Value |
|-------|-------|
| Used in | `ocr_engine.py` — Image preprocessing for OCR |
| License | **Apache 2.0** (wrapper code) + third-party binary licenses (FFmpeg/LGPL, etc.) |
| Source | https://pypi.org/project/opencv-python-headless/ |
| Obligation | The OpenCV project itself is Apache 2.0, but the pip wheel may
contain or link to binaries under other licenses (e.g., FFmpeg under LGPL).
Review the wheel's LICENSE file for specifics. |
| Recommendation | Retain this license notice in documentation and review the
opencv-python-headless wheel for bundled third-party binary licenses before
commercial distribution. |

---

## Low-Risk Licenses (Permissive / Compatible)

| Dependency | License | Notes |
|------------|---------|-------|
| rapidocr-onnxruntime | **Apache-2.0** | Retain NOTICE if required |
| onnxruntime | **MIT** | Retain license text |
| python-docx | **MIT** | Freely usable |
| diff-match-patch | **Apache-2.0** | Retain NOTICE if required |
| FastAPI | **MIT** | Freely usable |
| Starlette | **BSD-3-Clause** | Freely usable |
| Uvicorn | **BSD-3-Clause** | Freely usable |
| Streamlit | **Apache-2.0** | Retain license text |
| openpyxl | **MIT** | Freely usable |
| python-multipart | **Apache-2.0** | Retain notice |
| jinja2 | **BSD-3-Clause** | Freely usable |
| cryptography | **Apache-2.0 / BSD** | Dual-licensed, freely usable |
| python-dateutil | **Apache-2.0** | Retain notice |
| regex | **Apache-2.0** | Retain notice |
| numpy | **BSD-3-Clause** | Freely usable |
| pytest / pytest-cov | **MIT** | Development only |

---

## LLM Service Data Handling / LLM 数据处理说明

| Provider | Data Handling | Recommendation |
|----------|--------------|----------------|
| **Ollama** (local) | All processing is local. No data leaves the machine. | Safe for all use cases. |
| **Claude API** (Anthropic) | Contract text is sent to Anthropic's API. Subject to
Anthropic's data processing terms. | Default **disabled**. Only enable with
explicit customer authorization and appropriate data processing agreements. |

---

## Export Format Licenses

Reports exported in **PDF format** via `fpdf2` carry the LGPL-3.0-only license
obligations of that library. If you redistribute generated PDF reports
externally, consult legal counsel regarding whether the LGPL obligations
apply to your use case.

---

## Additional Notes

- This document was generated based on PyPI metadata and official project
documentation as of 2026-05-25. License terms may change; please verify
before distribution.
- SPDX identifiers follow the [SPDX License List](https://spdx.org/licenses/).
- For a machine-readable bill of materials (SBOM), run:
  ```bash
  pip list --format=json > sbom.json
  ```
