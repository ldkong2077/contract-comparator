# 截图说明 / Screenshots Guide

本目录用于存放项目截图，供 README 和文档使用。

## 需要的截图

| 文件名 | 说明 | 获取方式 |
|--------|------|----------|
| `cli_output.png` | CLI 命令行输出示例 | 运行 CLI 命令后截取终端 |
| `streamlit_ui.png` | Streamlit Web UI 界面 | 启动 Streamlit 后截取浏览器 |
| `api_swagger.png` | FastAPI Swagger 文档 | 启动 API 后访问 /docs 截取 |

## 获取截图的步骤

### 1. CLI 输出截图

```bash
# 安装依赖
pip install -r requirements.lock

# 运行对比命令（需要准备测试文件）
python -m contract_comparator.cli.main compare \
    --word test_contract.docx \
    --pdf test_scan.pdf \
    --output ./output

# 截取终端输出
```

### 2. Streamlit UI 截图

```bash
# 启动 Streamlit
streamlit run src/contract_comparator/web/app_streamlit.py

# 浏览器访问 http://localhost:8501
# 截取界面
```

### 3. FastAPI Swagger 截图

```bash
# 启动 FastAPI
uvicorn contract_comparator.api.api_server:app --reload

# 浏览器访问 http://localhost:8080/docs
# 截取 Swagger 界面
```

## 截图规范

- 格式：PNG
- 宽度：1200px（推荐）
- 文件大小：< 500KB
- 命名：小写英文 + 下划线

## 临时替代方案

在正式截图制作完成前，README 中的截图引用会显示为空白。建议尽快补充实际截图。
