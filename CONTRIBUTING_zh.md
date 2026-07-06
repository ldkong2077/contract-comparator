# 贡献指南 / Contributing Guide

[English](CONTRIBUTING.md) | 中文

感谢您对合同扫描件比对项目的关注！我们欢迎任何形式的贡献。

## 开发流程

1. Fork 本仓库，基于 `main` 分支创建您的分支
2. 如果添加了新功能，请编写相应的测试
3. 如果修改了 API，请更新相关文档
4. 确保测试套件通过
5. 确保代码符合规范
6. 提交 Pull Request

## 代码规范

### 代码风格

- 遵循 [PEP 8](https://www.python.org/dev/peps/pep-0008/) Python 代码规范
- 所有函数签名使用类型注解
- 最大行长度：120 字符
- 变量命名使用描述性名称（中文拼音或英文均可）

### 项目结构

```
src/contract_comparator/
├── __init__.py           # 包初始化
├── config.py             # 全局配置
├── database.py           # 数据库层
├── error_handler.py      # 错误处理
├── security.py           # 安全模块
├── utils.py              # 工具函数
├── api/                  # FastAPI REST API
├── cli/                  # CLI 入口
├── compare/              # 比对引擎
├── engine/               # 核心处理引擎
├── export/               # 导出模块
├── llm/                  # LLM 集成
└── web/                  # Streamlit UI
```

### 注释规范

- 使用中文注释，提高可读性
- 模块级 docstring 说明模块用途
- 类级 docstring 说明类的功能和用法
- 方法级 docstring 说明参数、返回值、异常

## 提交信息规范

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### 类型说明

| 类型 | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(ocr): 添加 EasyOCR 后备引擎` |
| `fix` | Bug 修复 | `fix(comparator): 处理空日期列表` |
| `docs` | 文档更新 | `docs(api): 更新 API 参考文档` |
| `style` | 代码格式（不影响功能） | `style(security): 格式化代码` |
| `refactor` | 重构（不新增功能/修复 Bug） | `refactor(database): 优化查询性能` |
| `test` | 测试相关 | `test(excel): 添加 Excel 对比测试` |
| `chore` | 构建/工具链更新 | `chore(ci): 更新 GitHub Actions` |
| `perf` | 性能优化 | `perf(ocr): 优化图片预处理` |
| `ci` | CI/CD 配置 | `ci(test): 添加覆盖率检查` |
| `security` | 安全相关 | `security(auth): 修复 API Key 泄露` |

### 范围 (scope)

- `cli` — 命令行界面
- `api` — REST API
- `web` — Streamlit UI
- `ocr` — OCR 引擎
- `compare` — 比对引擎
- `llm` — LLM 集成
- `export` — 导出模块
- `security` — 安全模块
- `database` — 数据库
- `docs` — 文档

### 示例

```bash
feat(ocr): 添加 EasyOCR 后备引擎

- 支持 RapidOCR 失败时自动切换到 EasyOCR
- 添加引擎切换日志记录
- 更新配置文件支持引擎优先级设置

Closes #123
```

## 测试要求

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行带覆盖率的测试
pytest tests/ --cov=src/contract_comparator --cov-report=html

# 运行特定测试文件
pytest tests/test_security.py -v
```

### 测试覆盖率

- 最低覆盖率要求：60%
- 新功能必须包含测试
- Bug 修复必须包含回归测试

### 测试文件命名

- 单元测试：`test_<module>.py`
- 集成测试：`test_integration_<feature>.py`
- 测试函数：`test_<function_name>.py`

## Pull Request 流程

### 提交前检查

- [ ] 代码符合 PEP 8 规范
- [ ] 所有测试通过
- [ ] 覆盖率不低于 60%
- [ ] 更新了相关文档
- [ ] 更新了 CHANGELOG.md
- [ ] 提交信息符合 Conventional Commits 规范

### PR 描述模板

```markdown
## 变更说明

简要描述本次变更的内容...

## 变更类型

- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 其他 (chore)

## 测试

- [ ] 已添加/更新测试用例
- [ ] 本地测试通过

## 相关 Issue

Closes #<issue_number>
```

## 开发环境搭建

### 前置条件

- Python 3.10+
- pip
- Git

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/ldkong2077/contract-comparator.git
cd contract-comparator

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.lock

# 4. 安装开发依赖
pip install -e ".[dev]"

# 5. 验证安装
pytest tests/ -v
```

### IDE 配置

推荐使用 VS Code 或 PyCharm，并安装以下插件：

- Python
- Pylance
- Pylint 或 Flake8
- Black（代码格式化）

## 代码审查标准

### 必须满足

- ✅ 代码可读性强，注释清晰
- ✅ 测试覆盖率达标
- ✅ 无安全漏洞
- ✅ 符合项目代码规范

### 鼓励做到

- ✅ 提交前自我审查
- ✅ 添加代码注释说明复杂逻辑
- ✅ 更新相关文档
- ✅ 考虑边界情况

## 社区准则

- 尊重每一位贡献者
- 建设性地提出建议
- 专注于技术讨论
- 遵循项目的行为准则

## 获取帮助

- GitHub Issues：报告 Bug 或提出功能建议
- 邮件：info@numboxhub.com
- 安全问题：info@numboxhub.com

## 许可证

贡献代码即表示您同意将代码置于 [MIT 许可证](LICENSE) 下。
