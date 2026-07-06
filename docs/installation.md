# Installation Guide / 安装指南

## Prerequisites / 前置要求

| Requirement | Minimum Version | Notes |
|-------------|----------------|-------|
| Python | 3.10 | 3.12 recommended |
| pip | 21.0 | Latest recommended |
| RAM | 4 GB | 8 GB for Docker + Ollama |
| Disk | 2 GB | Includes OCR model downloads |

## Standard Installation / 标准安装

### From PyPI (Coming Soon)

```bash
pip install contract-comparator
```

### From Source

```bash
# Clone the repository
git clone https://github.com/ldkong2077/contract-comparator.git
cd contract-comparator

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies（锁定版本）
pip install -r requirements.lock

# Optional: Install dev dependencies
pip install -e ".[dev]"
```

### Verify Installation

```bash
# Check CLI
python main.py --help

# Run tests
pytest -v
```

## Docker Installation / Docker 安装

### Single Service

```bash
# Build image
docker build -t contract-comparator .

# Run API server
docker run -p 8080:8080 contract-comparator
```

### Multi-Service (Recommended)

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

This starts:
- **contract-api** (FastAPI) on `:8080`
- **contract-ui** (Streamlit) on `:8501`
- **ollama** (LLM service) on `:11434`

### Docker Images

Pre-built images are available via GitHub Container Registry:

```bash
docker pull ghcr.io/ldkong2077/contract-comparator:latest
```

## Optional Dependencies / 可选依赖

### Tesseract OCR (Fallback Engine)

**Windows:**
1. Download from [GitHub UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install and add to PATH

**Ubuntu/Debian:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-chi-sim
```

**macOS:**
```bash
brew install tesseract
```

### Ollama (Local LLM)

```bash
# Install Ollama
# https://ollama.ai/download

# Pull a model
ollama pull qwen3.5-0.8b

# Verify
ollama list
```

## Post-Installation / 安装后配置

### 1. Configure API Keys

```bash
# Copy template
cp config/api_keys.json.template config/api_keys.json

# Edit with your keys
# See Configuration Guide for details
```

### 2. Set Environment Variables

```bash
# Copy .env.example
cp .env.example .env

# Edit .env with your settings
```

### 3. (Optional) Generate Encryption Key

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key()
print(key.decode())
# Add this to your .env as ENCRYPTION_KEY
```

## Troubleshooting / 故障排除

### Common Issues

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: rapidocr_onnxruntime` | Ensure you have internet access for first-run model download |
| OCR returns garbled text | Install Chinese language pack for Tesseract |
| `docker-compose: command not found` | Install Docker Compose v2 |
| Port already in use | Change ports in `docker-compose.yml` or use `--port` flag |
| Ollama connection refused | Ensure Ollama is running: `ollama serve` |

### Getting Help

- Open an issue on GitHub
- Check existing issues for similar problems
