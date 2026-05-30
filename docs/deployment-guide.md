# Deployment Guide / 部署指南

## Overview / 概述

This guide covers deployment of Contract Comparator for **internal enterprise trial use**.
The project is currently at **Beta / Pilot** stage and is not recommended for direct public
SaaS deployment.

---

## 1. Recommended Deployment Architecture

### Single-Node Docker (Recommended for Pilot)

```
┌─────────────────────────────────────────┐
│  Docker Host (Linux / macOS / Windows)   │
│                                          │
│  ┌──────────┐  ┌──────────┐             │
│  │ Streamlit │  │ FastAPI  │             │
│  │ (Port     │  │ (Port    │             │
│  │  8501)    │  │  8080)   │             │
│  └─────┬─────┘  └────┬─────┘             │
│        │              │                   │
│  ┌─────┴──────────────┴──────┐           │
│  │    Shared Volume:         │           │
│  │    - ./output (results)   │           │
│  │    - ./profiles (config)  │           │
│  └───────────────────────────┘           │
│                                          │
│  ┌──────────────────────────┐            │
│  │  Ollama (Optional)       │            │
│  │  Port 11434              │            │
│  └──────────────────────────┘            │
└─────────────────────────────────────────┘
```

### Prerequisites / 前置条件

- Docker Engine 24+ & Docker Compose v2+
- 4 GB RAM minimum, 8 GB recommended
- 10 GB free disk space (includes OCR models)
- Network: internal/LAN only (not exposed to public internet)

---

## 2. Standard Deployment

### 2.1 Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/contract-comparator/contract-comparator.git
cd contract-comparator

# 2. Configure environment
cp .env.example .env
# Edit .env as needed (see Configuration section)

# 3. Start services
docker compose up -d

# 4. Verify
curl http://localhost:8080/api/v1/health

# 5. Access
# Streamlit UI: http://localhost:8501
# API Docs:     http://localhost:8080/docs
```

### 2.2 First-Run Setup

On first startup, the API automatically generates a default admin API Key.
The masked key is printed in the container logs:

```bash
docker logs contract-comparator-api 2>&1 | grep "API Key"
# Example output:
# API Key (masked): cc_a...bcde
# Key ID: a1b2c3d4e5f6g7h8
```

Save this key for API access. In production, generate custom keys via the API.

### 2.3 Service Ports

| Service | Port | Description |
|---------|------|-------------|
| Streamlit UI | 8501 | Web dashboard |
| FastAPI | 8080 | REST API + Swagger |
| Ollama (optional) | 11434 | Local LLM |

---

## 3. Configuration / 配置

### 3.1 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `AUTH_ENABLED` | `true` | Enable API Key authentication |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_RPM` | `30` | Max requests per minute per key |
| `RATE_LIMIT_BURST` | `5` | Max burst requests |
| `MAX_FILE_SIZE_MB` | `50` | Maximum upload file size |
| `MAX_BATCH_PAIRS` | `10` | Maximum batch comparison pairs |
| `LLM_ENABLED` | `false` | Enable LLM features |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `CLAUDE_API_KEY` | (empty) | Claude API key |
| `OUTPUT_DIR` | `./output` | Output directory for results |

### 3.2 Production-Ready Configuration

For internal deployment, add the following to your `.env`:

```bash
# Security
AUTH_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_RPM=60
RATE_LIMIT_BURST=10

# Resource limits
MAX_FILE_SIZE_MB=50
MAX_BATCH_PAIRS=10

# Logging
LOG_LEVEL=INFO

# LLM (disable cloud by default)
LLM_ENABLED=false
```

### 3.3 Docker Resource Limits

Add resource constraints to `docker-compose.yml` for production use:

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
  streamlit:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 4. Docker Image Build

### 4.1 Build from Source

```bash
docker build -t contract-comparator:latest .
docker build -t contract-comparator:4.0.0 .
```

### 4.2 Image Layers

The Dockerfile creates the following layers:
1. System dependencies (OpenCV, ONNX Runtime)
2. Python dependencies (~500 MB with OCR models)
3. Application code (~2 MB)
4. Runtime directories

Total image size: approximately 1.2 GB (includes RapidOCR models).

---

## 5. Network Security

### 5.1 Firewall Rules

| Source | Destination | Port | Protocol | Purpose |
|--------|-------------|------|----------|---------|
| User browser | Streamlit | 8501 | HTTP | Web UI |
| User/scripts | FastAPI | 8080 | HTTP | API access |
| Streamlit | FastAPI | 8080 | HTTP | Internal communication |
| API | Ollama (optional) | 11434 | HTTP | LLM inference |

### 5.2 Reverse Proxy (Recommended)

For internal deployments with multiple users, place behind a reverse proxy:

```nginx
server {
    listen 443 ssl;
    server_name contract-compare.internal.company.com;

    ssl_certificate /etc/ssl/certs/company.crt;
    ssl_certificate_key /etc/ssl/private/company.key;

    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5.3 VPN Recommendation

Access should be restricted to internal network or VPN. Do not expose directly
to the public internet without proper security review.

---

## 6. Data Storage

### 6.1 Volume Mounts

```yaml
volumes:
  - ./output:/app/output       # Comparison results, export files
  - ./profiles:/app/profiles   # Industry presets (read-only recommended)
  - ./data:/app/data           # SQLite database
```

### 6.2 Backup Strategy

```bash
# Backup SQLite database
cp ./data/contract_comparator.db ./backups/contract_comparator_$(date +%Y%m%d).db

# Backup output files
tar -czf ./backups/output_$(date +%Y%m%d).tar.gz ./output/

# Restore
cp ./backups/contract_comparator_20260101.db ./data/contract_comparator.db
```

---

## 7. Verification Checklist

- [ ] All services start without errors: `docker compose ps`
- [ ] Health endpoint returns 200: `curl http://localhost:8080/api/v1/health`
- [ ] Authentication works: `curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/profiles`
- [ ] File upload works (basic format check)
- [ ] OCR processes at least one test document
- [ ] Logs are being written to the output directory
- [ ] Container restart policy works: `docker compose restart`

---

## 8. Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| OCR returns empty | Model not downloaded | First run downloads models; check network connectivity |
| API Key authentication fails | Wrong key or auth disabled | Check `AUTH_ENABLED=true` and verify key |
| Streamlit cannot connect to API | API not ready or port mismatch | Wait for API healthcheck, check `API_BASE_URL` |
| Container exits immediately | Port conflict or missing dependencies | Check `docker logs <container>` |
| Out of memory | Large PDF processing | Add `--memory` limits to Docker |
