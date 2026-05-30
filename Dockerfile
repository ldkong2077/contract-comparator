# ============================================================
# 合同比对专业版 Dockerfile
# 支持 Streamlit UI (8501) 和 FastAPI (8080) 双服务
# ============================================================

FROM python:3.11-slim

LABEL maintainer="contract-comparator"
LABEL description="合同扫描件与 Word 文档比对工具"
LABEL version="4.0.0"

# ---- 系统依赖 ----
# libgl1-mesa-glx, libglib2.0-0, libsm6, libxext6, libxrender-dev: OpenCV 依赖
# libgomp1: ONNX Runtime / OpenMP 依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- 创建非 root 用户 ----
RUN groupadd -r app && useradd -r -g app -m -s /bin/bash app

# ---- 工作目录 ----
WORKDIR /app

# ---- Python 依赖（锁定版本）----
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

# ---- 复制源码并安装包 ----
COPY --chown=app:app . .

# 安装为可编辑包（src/ 布局支持 contract_comparator.* 导入）
RUN pip install --no-cache-dir -e .

# ---- 创建运行时目录 ----
RUN mkdir -p /app/output /app/profiles /app/temp && \
    chown -R app:app /app/output /app/profiles /app/temp

# ---- 切换用户 ----
USER app

# ---- 环境变量 ----
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    API_HOST=0.0.0.0 \
    API_PORT=8080

# ---- 端口 ----
EXPOSE 8501 8080

# ---- 健康检查（Streamlit）----
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# ---- 默认启动 Streamlit UI ----
CMD ["streamlit", "run", "--server.port=8501", "--server.address=0.0.0.0", "src/contract_comparator/web/app_streamlit.py"]

# ---- 启用 FastAPI 时使用: ----
# CMD ["uvicorn", "contract_comparator.api.api_server:app", "--host", "0.0.0.0", "--port", "8080"]