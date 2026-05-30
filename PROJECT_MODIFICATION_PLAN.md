# Contract Document Comparator - 开源发布修改计划

**项目版本**: v4.0.0  
**计划制定日期**: 2026-05-30  
**审核评分**: 75/100 → 目标 95/100  

---

## 目录

1. [执行摘要](#执行摘要)
2. [问题清单与优先级矩阵](#问题清单与优先级矩阵)
3. [第一阶段：发布前必修 (P0)](#第一阶段发布前必修-p0)
4. [第二阶段：商业化准备 (P1)](#第二阶段商业化准备-p1)
5. [第三阶段：质量提升 (P2)](#第三阶段质量提升-p2)
6. [第四阶段：持续改进 (P3)](#第四阶段持续改进-p3)
7. [资源需求与风险评估](#资源需求与风险评估)
8. [质量验收标准](#质量验收标准)
9. [效果评估机制](#效果评估机制)
10. [附录：文件变更清单](#附录文件变更清单)

---

## 执行摘要

| 指标 | 当前状态 | 目标状态 |
|------|----------|----------|
| **总体评分** | 75/100 | 95/100 |
| **阻塞项 (P0)** | 4 项 | 0 项 |
| **高优先级 (P1)** | 5 项 | 0 项 |
| **中优先级 (P2)** | 4 项 | 0 项 |
| **低优先级 (P3)** | 3 项 | 持续改进 |
| **预计完成时间** | — | 2-3 周 |

**核心问题**: 项目技术架构完善，但"有架子无内容"——README 描述与实际代码不符、截图为空、示例文件缺失、商业转化通道不畅。

---

## 问题清单与优先级矩阵

### P0 — 阻塞项（必须在发布前修复）

| # | 问题 | 位置 | 影响 | 预估工时 |
|---|------|------|------|----------|
| 1 | README 项目结构描述与实际不符 | README.md:436-493 | 误导开发者，损害专业形象 | 1h |
| 2 | Screenshots 目录为空 | docs/images/ | 无视觉展示，首次体验差 | 3h |
| 3 | Examples 目录为空 | examples/api/, examples/profiles/ | 新用户无法快速上手 | 2h |
| 4 | CODE_OF_CONDUCT 联系方式未填写 | .github/CODE_OF_CONDUCT.md:55 | 无法报告违规行为 | 5min |

### P1 — 高优先级（发布后 1 周内修复）

| # | 问题 | 位置 | 影响 | 预估工时 |
|---|------|------|------|----------|
| 5 | 商业版联系方式缺失 | README.md | 无法转化潜在客户 | 2h |
| 6 | 邮箱域名可能未注册 | SECURITY.md:21, pyproject.toml | 安全漏洞无法报告 | 1-2d |
| 7 | 功能差异化不清晰 | README.md | 商业版价值感不足 | 4h |
| 8 | CLI 用法不一致 | README.md vs main.py | 用户困惑 | 1h |
| 9 | 模块内导入路径错误 | main.py:177, 221 | 运行时错误 | 30min |

### P2 — 中优先级（发布后 2 周内修复）

| # | 问题 | 位置 | 影响 | 预估工时 |
|---|------|------|------|----------|
| 10 | 测试覆盖率无最低阈值 | pyproject.toml | 代码质量无法保证 | 1h |
| 11 | usage.md 截图占位 | docs/usage.md:84-85 | 文档不完整 | 1h |
| 12 | _test_security.py 命名异常 | tests/_test_security.py | 被 pytest 默认忽略 | 30min |
| 13 | docker-compose version 已弃用 | docker-compose.yml:5 | 构建警告 | 5min |

### P3 — 低优先级（持续改进）

| # | 问题 | 位置 | 影响 | 预估工时 |
|---|------|------|------|----------|
| 14 | 缺少 CONTRIBUTING 中文版 | CONTRIBUTING.md | 国际贡献者门槛 | 2h |
| 15 | docs/index.html 存在 | docs/index.html | 用途不明 | 30min |
| 16 | __pycache__ 残留 | 旧版副本目录 | 仓库臃肿 | 15min |

---

## 第一阶段：发布前必修 (P0)

**时间**: 第 1-3 天  
**目标**: 消除所有阻塞项，确保首次发布专业性

### 任务 1.1: 重写 README 项目结构 (1h)

**文件**: `README.md` 第 436-493 行

**当前问题**:
```
├── api_server.py               # FastAPI REST API (~1960 lines)
├── app_streamlit.py            # Streamlit web UI (~2350 lines)
├── auth.py                     # Authentication & RBAC (~350 lines)
├── comparator.py               # Field comparison engine
├── config.py                   # Global configuration
├── database.py                 # SQLite database layer (~1000 lines)
...
```

**实际结构**:
```
contract-comparator/
├── src/
│   └── contract_comparator/
│       ├── __init__.py
│       ├── api/                    # FastAPI REST API
│       │   └── server.py
│       ├── cli/                    # CLI 入口
│       │   └── main.py
│       ├── compare/                # 比对引擎
│       │   └── comparator.py
│       ├── config.py               # 全局配置
│       ├── database.py             # SQLite 数据库层
│       ├── engine/                 # OCR/LLM 引擎
│       │   ├── ocr_engine.py
│       │   └── llm_engine.py
│       ├── error_handler.py        # 错误处理
│       ├── export/                 # 导出模块
│       │   └── report_exporter.py
│       ├── llm/                    # LLM 集成
│       │   └── engine.py
│       ├── profiles.py             # 行业预设
│       ├── security.py             # 安全层
│       ├── utils.py                # 工具函数
│       └── web/                    # Streamlit UI
│           └── app.py
├── tests/                          # 测试套件
├── docs/                           # 文档
├── examples/                       # 示例文件
├── config/                         # 配置模板
└── ...
```

**执行步骤**:
1. 删除第 436-493 行旧的项目结构
2. 替换为实际的 src/ 布局
3. 保留注释风格和行数估算
4. 添加关键模块说明

**验收标准**:
- [ ] 结构与 `src/contract_comparator/` 目录完全一致
- [ ] 所有模块路径正确
- [ ] 中英文注释完整

---

### 任务 1.2: 补充 Screenshots (3h)

**目录**: `docs/images/`

**需要的截图**:
1. `cli_output.png` — CLI 命令行输出示例
2. `streamlit_ui.png` — Streamlit Web UI 界面
3. `api_swagger.png` — FastAPI Swagger 文档

**执行步骤**:
1. 运行项目，获取各界面截图
2. 压缩图片（建议宽度 1200px，文件 < 500KB）
3. 保存到 `docs/images/` 目录
4. 更新 README.md 中的图片引用

**截图获取方法**:

```bash
# 1. CLI 输出截图
python -m contract_comparator.cli.main compare \
    --word sample.docx --pdf sample.pdf --output ./output

# 2. Streamlit UI 截图
streamlit run src/contract_comparator/web/app.py
# 在浏览器中截图

# 3. API Swagger 截图
uvicorn src.contract_comparator.api.server:app --reload
# 访问 http://localhost:8000/docs 并截图
```

**验收标准**:
- [ ] 3 张截图清晰可见
- [ ] 图片大小 < 500KB
- [ ] README.md 中图片引用正确

---

### 任务 1.3: 创建 Examples 示例 (2h)

**目标文件**:
- `examples/api/curl_examples.sh`
- `examples/api/python_client.py`
- `examples/profiles/custom_profile.json`

**文件内容要求**:

**curl_examples.sh**:
```bash
#!/bin/bash
# 合同比对工具 API 调用示例
# Usage: ./curl_examples.sh

BASE_URL="http://localhost:8000"

# 1. 健康检查
echo "=== 健康检查 ==="
curl -s "$BASE_URL/health" | jq .

# 2. 上传文件对比
echo "=== 文件对比 ==="
curl -X POST "$BASE_URL/api/v1/compare" \
    -F "word_file=@contract.docx" \
    -F "pdf_file=@scan.pdf" | jq .

# 3. 获取对比结果
echo "=== 获取结果 ==="
curl -s "$BASE_URL/api/v1/results/{task_id}" | jq .
```

**python_client.py**:
```python
"""
合同扫描件比对工具 - Python 客户端示例
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def health_check():
    """检查 API 服务状态"""
    response = requests.get(f"{BASE_URL}/health")
    return response.json()

def compare_documents(word_file: str, pdf_file: str):
    """上传文档进行对比"""
    with open(word_file, 'rb') as wf, open(pdf_file, 'rb') as pf:
        files = {
            'word_file': (word_file, wf, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
            'pdf_file': (pdf_file, pf, 'application/pdf')
        }
        response = requests.post(f"{BASE_URL}/api/v1/compare", files=files)
    return response.json()

def get_result(task_id: str):
    """获取对比结果"""
    response = requests.get(f"{BASE_URL}/api/v1/results/{task_id}")
    return response.json()

if __name__ == "__main__":
    # 示例用法
    print("健康检查:", health_check())
    # result = compare_documents("contract.docx", "scan.pdf")
    # print("对比结果:", json.dumps(result, ensure_ascii=False, indent=2))
```

**custom_profile.json**:
```json
{
    "name": "自定义合同模板",
    "description": "适用于采购合同的字段提取配置",
    "version": "1.0",
    "fields": {
        "contract_no": {
            "label": "合同编号",
            "patterns": ["合同编号[：:]\\s*(\\S+)", "Contract No[.:]\\s*(\\S+)"],
            "type": "string",
            "required": true
        },
        "amount": {
            "label": "合同金额",
            "patterns": ["金额[：:]\\s*([\\d,\\.]+)", "Amount[：:]\\s*([\\d,\\.]+)"],
            "type": "currency",
            "required": true
        },
        "date": {
            "label": "签订日期",
            "patterns": ["日期[：:]\\s*(\\d{4}[-/]\\d{1,2}[-/]\\d{1,2})"],
            "type": "date",
            "required": true
        },
        "parties": {
            "label": "合同双方",
            "patterns": ["甲方[：:](.+?)\\s*乙方[：:](.+)"],
            "type": "text",
            "required": true
        }
    }
}
```

**验收标准**:
- [ ] curl_examples.sh 可执行
- [ ] python_client.py 语法正确
- [ ] custom_profile.json 格式有效
- [ ] 更新 examples/README.md 引用

---

### 任务 1.4: 修复 CODE_OF_CONDUCT (5min)

**文件**: `.github/CODE_OF_CONDUCT.md` 第 55 行

**当前内容**:
```
[INSERT CONTACT METHOD]
```

**修改为**:
```
info@numboxhub.com
```

**执行步骤**:
1. 打开文件，定位第 55 行
2. 替换占位符为实际邮箱

**验收标准**:
- [x] 占位符已替换
- [x] 邮箱格式正确

---

### 任务 1.5: 统一 CLI 用法 (1h)

**文件**: `README.md` Quick Start 部分

**当前问题**: README 使用旧版扁平参数 `python main.py --word ... --pdf ...`

**修改为子命令模式**:
```bash
# 文件对比
python -m contract_comparator.cli.main compare \
    --word contract.docx \
    --pdf scan.pdf \
    --output ./output

# Excel 对比
python -m contract_comparator.cli.main excel \
    --file-a data1.xlsx \
    --file-b data2.xlsx

# OCR 识别
python -m contract_comparator.cli.main ocr \
    --input scan.pdf \
    --output ./output
```

**验收标准**:
- [ ] 所有 CLI 示例使用子命令
- [ ] 示例命令可实际执行

---

## 第二阶段：商业化准备 (P1)

**时间**: 第 4-7 天  
**目标**: 建立有效的开源→商业转化通道

### 任务 2.1: 域名与邮箱配置 (1-2d)

**行动项**:
1. ~~注册 `contract-comparator.dev` 域名~~ (已完成，使用 numboxhub.com 统一邮箱)
2. 配置邮箱: `info@numboxhub.com` — 统一联系邮箱
3. 配置邮件转发（可选）

**验收标准**:
- [x] 邮箱可收发邮件
- [x] SECURITY.md 和 pyproject.toml 中邮箱正确

---

### 任务 2.2: README 商业章节 (2h)

**在 README.md 中添加**:

```markdown
## 商业版本 / Commercial Version

本开源版本仅供本地/内网试用与评估。商业版本提供以下增强功能：

| 功能 | 开源版 | 商业版 |
|------|--------|--------|
| OCR 文字识别 | ✅ | ✅ |
| 字段级对比 | ✅ | ✅ |
| 全文差异 | ✅ | ✅ |
| Excel 对比 | ✅ | ✅ |
| LLM 语义分析 | ✅ | ✅ |
| RBAC 权限控制 | ❌ | ✅ |
| 审计日志 | ❌ | ✅ |
| 批量处理 API | ❌ | ✅ |
| 企业级部署支持 | ❌ | ✅ |
| 7x24 技术支持 | ❌ | ✅ |

### 联系我们

- **综合咨询**: info@numboxhub.com
- **安全报告**: info@numboxhub.com

---

> **注意**: 如需生产环境部署、企业级功能或技术支持，请联系项目维护团队获取商业版本信息。
```

**验收标准**:
- [ ] 功能对比表清晰
- [ ] 联系方式可访问
- [ ] 与开源版本声明不冲突

---

### 任务 2.3: 功能差异化设计 (4h)

**策略建议**:

| 功能类别 | 开源版保留 | 商业版独占 |
|----------|------------|------------|
| **核心对比** | ✅ 文件对比、字段提取、全文差异 | — |
| **导出格式** | ✅ JSON、TXT、HTML | PDF 报告、Word 报告 |
| **OCR 引擎** | ✅ Tesseract、PaddleOCR | 商业 OCR API 集成 |
| **LLM 集成** | ✅ Ollama 本地 | Claude/GPT-4 云服务 |
| **用户管理** | ❌ 无 | RBAC、SSO、LDAP |
| **审计日志** | ❌ 无 | 完整审计追踪 |
| **批量处理** | ❌ 单文件 | 批量 API、队列 |
| **部署支持** | Docker 单机 | K8s 集群、高可用 |

**执行步骤**:
1. 评估各功能的实现成本
2. 确定开源版功能边界
3. 更新 README 功能表格
4. 在代码中添加商业版功能提示（如 RBAC 模块）

**验收标准**:
- [ ] 功能边界清晰
- [ ] 开源版核心功能完整
- [ ] 商业版价值明确

---

### 任务 2.4: 模块导入修复 (30min)

**文件**: `src/contract_comparator/cli/main.py`

**修改 1** (第 177 行):
```python
# 当前
from database import DatabaseManager

# 修改为
from contract_comparator.database import DatabaseManager
```

**修改 2** (第 221 行):
```python
# 当前
from excel_comparator import ExcelComparator

# 修改为
from contract_comparator.compare.excel_comparator import ExcelComparator
```

**验收标准**:
- [ ] 导入路径正确
- [ ] 无运行时 ImportError
- [ ] 测试通过

---

## 第三阶段：质量提升 (P2)

**时间**: 第 8-14 天  
**目标**: 提升代码质量和开发者体验

### 任务 3.1: 测试覆盖率阈值 (1h)

**文件**: `pyproject.toml`

**添加配置**:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=contract_comparator --cov-report=html --cov-fail-under=60"

[tool.coverage.run]
source = ["src/contract_comparator"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.",
    "raise NotImplementedError",
]
```

**验收标准**:
- [ ] 覆盖率阈值生效
- [ ] CI 中 coverage 检查通过
- [ ] 文档中说明最低覆盖率要求

---

### 任务 3.2: usage.md 截图 (1h)

**文件**: `docs/usage.md` 第 84-85 行

**当前内容**:
```markdown
### Screenshot

```
[Streamlit UI will display here]
```
```

**修改为**:
```markdown
### Screenshot

![Streamlit UI 截图](images/streamlit_ui.png)

*图：Streamlit Web UI 主界面，支持文件上传和实时对比*
```

**验收标准**:
- [ ] 截图路径正确
- [ ] 图片显示正常

---

### 任务 3.3: 测试文件重命名 (30min)

**文件**: `tests/_test_security.py`

**操作**:
```bash
cd tests/
mv _test_security.py test_security.py
```

**或保留原文件**，在 `pyproject.toml` 中添加说明:
```toml
[tool.pytest.ini_options]
# _test_security.py 为遗留测试文件，暂不纳入默认测试套件
```

**验收标准**:
- [ ] 测试文件可被 pytest 发现
- [ ] 测试通过

---

### 任务 3.4: Docker Compose 更新 (5min)

**文件**: `docker-compose.yml` 第 5 行

**删除**:
```yaml
version: "3.9"
```

**原因**: Compose V2 不再需要 `version` 字段，保留会产生警告

**验收标准**:
- [ ] `docker compose up` 无警告
- [ ] 服务正常启动

---

## 第四阶段：持续改进 (P3)

**时间**: 持续进行  
**目标**: 长期社区建设和文档完善

### 任务 4.1: 中文贡献指南 (2h)

创建 `CONTRIBUTING_zh.md`，内容:
- 开发环境搭建
- 代码规范（中文注释）
- 提交规范（Conventional Commits）
- PR 流程
- 测试要求

在 `CONTRIBUTING.md` 顶部添加:
```markdown
[English](CONTRIBUTING.md) | [中文](CONTRIBUTING_zh.md)
```

---

### 任务 4.2: 清理遗留文件 (30min)

**检查**:
1. `docs/index.html` — 确认用途，删除或文档化
2. 旧版副本目录中的 `__pycache__` — 删除

```bash
find . -type d -name "__pycache__" -exec rm -rf {} +
```

---

## 资源需求与风险评估

### 人员需求

| 角色 | 人数 | 职责 |
|------|------|------|
| 开发工程师 | 1 | 代码修改、测试执行 |
| UI/截图设计 | 1 | 截图制作、视觉优化 |
| DevOps | 1 | 域名配置、CI/CD 验证 |

### 工具需求

| 工具 | 用途 | 备注 |
|------|------|------|
| 屏幕截图软件 | 制作文档截图 | 建议使用 Snipaste 或系统截图 |
| 域名注册服务 | 注册 contract-comparator.dev | — |
| 邮箱服务 | 配置企业邮箱 | 可用 Google Workspace 或腾讯企业邮 |

### 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 域名不可用 | 低 | 高 | 提前注册，准备备选域名 |
| 截图质量不佳 | 中 | 中 | 使用专业工具，团队评审 |
| 功能差异化引发社区不满 | 低 | 高 | 清晰沟通价值，保持开源核心 |
| 导入修复导致测试失败 | 低 | 中 | 修改后运行完整测试套件 |

---

## 质量验收标准

### 第一阶段验收 (P0)

- [ ] README.md 项目结构与 `src/` 目录完全一致
- [ ] `docs/images/` 包含 3 张截图且可正常显示
- [ ] `examples/api/` 和 `examples/profiles/` 包含可运行示例
- [ ] `.github/CODE_OF_CONDUCT.md` 无占位符文本

### 第二阶段验收 (P1)

- [ ] 至少 1 个邮箱地址可收发邮件
- [ ] README 包含商业版本章节和功能对比表
- [ ] 开源版与商业版功能边界清晰
- [ ] CLI 示例使用子命令模式
- [ ] 无 ImportError 运行时错误

### 第三阶段验收 (P2)

- [ ] `pytest` 执行通过且覆盖率 ≥ 60%
- [ ] `docs/usage.md` 截图正常显示
- [ ] 测试文件命名符合 pytest 规范
- [ ] `docker compose up` 无警告

---

## 效果评估机制

### 发布后指标监控

| 指标 | 目标值 | 监控频率 |
|------|--------|----------|
| GitHub Stars | 100+ (首月) | 每周 |
| Docker Pulls | 500+ (首月) | 每周 |
| 商业咨询邮件 | 5+ (首月) | 每周 |
| Issue 响应时间 | < 24 小时 | 每日 |
| PR 合并时间 | < 72 小时 | 每周 |
| 测试覆盖率 | > 60% | 每次 CI |

### 社区健康度评估

| 指标 | 目标 | 评估方法 |
|------|------|----------|
| Issue 标签使用率 | 100% | 每月审查 |
| PR 评论率 | > 50% | 每月统计 |
| 贡献者数量 | 5+ (季度) | GitHub Insights |
| 文档完整度 | > 90% | 每季度审查 |

### 持续改进流程

1. **每周**: 审查 GitHub Issues 和 PR
2. **每月**: 更新 CHANGELOG.md
3. **每季度**: 评估功能差异化策略
4. **每半年**: 审查开源协议合规性

---

## 附录：文件变更清单

### 需修改的文件

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| `README.md:436-493` | 重写项目结构 | P0 |
| `README.md` 多处 | 添加商业章节、更新 CLI 示例 | P1 |
| `.github/CODE_OF_CONDUCT.md:55` | 替换联系方式占位符 | P0 |
| `src/contract_comparator/cli/main.py:177` | 修复导入路径 | P1 |
| `src/contract_comparator/cli/main.py:221` | 修复导入路径 | P1 |
| `pyproject.toml` | 添加覆盖率阈值 | P2 |
| `docker-compose.yml:5` | 删除 version 字段 | P2 |
| `docs/usage.md:84-85` | 添加截图引用 | P2 |
| `tests/_test_security.py` | 重命名或文档化 | P2 |

### 需创建的文件

| 文件路径 | 内容 | 优先级 |
|----------|------|--------|
| `docs/images/cli_output.png` | CLI 输出截图 | P0 |
| `docs/images/streamlit_ui.png` | Streamlit UI 截图 | P0 |
| `docs/images/api_swagger.png` | API Swagger 截图 | P0 |
| `examples/api/curl_examples.sh` | curl 调用示例 | P0 |
| `examples/api/python_client.py` | Python 客户端示例 | P0 |
| `examples/profiles/custom_profile.json` | 自定义配置示例 | P0 |
| `CONTRIBUTING_zh.md` | 中文贡献指南 | P3 |

### 需删除的文件

| 文件/目录 | 原因 | 优先级 |
|-----------|------|--------|
| 旧版副本中的 `__pycache__/` | 清理编译缓存 | P3 |
| `docs/index.html`（如确认无用） | 遗留文件 | P3 |

---

## 时间线总览

```
第 1 天    ██████████ 任务 1.1 (README 项目结构)
第 2 天    ██████████ 任务 1.2 (截图制作)
第 3 天    ██████████ 任务 1.3 + 1.4 + 1.5 (示例 + CODE_OF_CONDUCT + CLI)
第 4-5 天  ██████████ 任务 2.1 (域名邮箱)
第 6 天    ██████████ 任务 2.2 + 2.4 (商业章节 + 导入修复)
第 7 天    ██████████ 任务 2.3 (功能差异化)
第 8-10 天 ██████████ 任务 3.1 + 3.2 (覆盖率 + 截图)
第 11 天   ██████████ 任务 3.3 + 3.4 (测试文件 + Docker)
第 12-14 天 █████████ 任务 4.1 + 4.2 (持续改进)
```

---

**计划制定人**: Sisyphus  
**最后更新**: 2026-05-30
