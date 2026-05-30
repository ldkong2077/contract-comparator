# Operations Guide / 运维指南

## Overview / 概述

This guide covers day-to-day operations, monitoring, maintenance, and troubleshooting
for Contract Comparator in an enterprise trial deployment.

---

## 1. Service Management

### 1.1 Starting and Stopping

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a specific service
docker compose restart api

# View running services
docker compose ps
```

### 1.2 Health Checks

The API provides a health endpoint:

```bash
curl http://localhost:8080/api/v1/health
```

Expected response:
```json
{
  "service": "contract_comparator_api",
  "version": "v4.0",
  "status": "healthy",
  "dependencies": {
    "ocr": true,
    "word_parser": true,
    "pdf_processor": true,
    "llm": false,
    "report_exporter": true
  },
  "uptime_seconds": 3600.0
}
```

Status values:
- `healthy`: All dependencies available
- `degraded`: Core dependencies (OCR, Word, PDF) available, optional components missing
- `unhealthy`: Core dependencies unavailable

### 1.3 Container Restart Policy

Docker Compose uses `restart: unless-stopped` by default, which means containers
will restart automatically unless explicitly stopped by an administrator.

---

## 2. Logging

### 2.1 Log Locations

| Component | Log Location | Format |
|-----------|-------------|--------|
| FastAPI | Container stdout | Structured text |
| Streamlit | Container stdout | Structured text |
| Audit Log | `./output/audit.log` | JSON Lines |
| Application Logs | Container stdout | Text with timestamps |

### 2.2 Viewing Logs

```bash
# Follow all service logs
docker compose logs -f

# Follow a specific service
docker compose logs -f api

# View last 100 lines
docker compose logs --tail=100 api

# Search for errors
docker compose logs api 2>&1 | grep -i error

# Export logs to file
docker compose logs api > logs/api_$(date +%Y%m%d).log
```

### 2.3 Log Rotation

Audit logs rotate automatically at 10 MB per file, keeping 5 backup files.
Container stdout logs are managed by Docker's logging driver. Configure
Docker daemon log rotation in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

### 2.4 Structured Log Fields

Application logs follow this format:
```
2026-01-15 14:30:00 [INFO] api_server: 任务 a1b2c3d4e5f6 完成，耗时 12.3s
2026-01-15 14:30:00 [ERROR] api_server: 未处理异常 [request_id=abc123def456]: Connection refused
```

Audit log entries (JSON Lines format):
```json
{"event": "comparison", "user_id": "key_abc123", "word_file": "contract.docx", "pdf_file": "scan.pdf", "timestamp": "2026-01-15T14:30:00"}
```

---

## 3. Monitoring

### 3.1 Basic Monitoring (Docker)

```bash
# Resource usage
docker stats

# Disk usage
du -sh ./output/
du -sh ./data/

# Container health
docker inspect --format='{{.State.Health.Status}}' contract-comparator-api
```

### 3.2 Prometheus / Grafana (Optional)

For advanced monitoring, add Prometheus metrics support:

1. Install `prometheus_client`: `pip install prometheus-client`
2. Add metrics endpoint to FastAPI (see architecture docs)
3. Configure Prometheus to scrape `http://api:8080/metrics`
4. Create Grafana dashboards for:
   - Request rate and latency
   - OCR processing time
   - Error rate by endpoint
   - Task queue depth
   - Memory and CPU usage

### 3.3 Key Metrics to Watch

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|------------------|--------------------|--------|
| API response time (p95) | > 30s | > 60s | Check OCR/LLM load |
| OCR failure rate | > 5% | > 15% | Check OCR model |
| Available disk space | < 20% | < 10% | Clean up output/data |
| Memory usage | > 70% | > 90% | Restart or scale |
| Task failure rate | > 5% | > 10% | Check logs |

---

## 4. Data Management

### 4.1 Backup

```bash
# Create backup directory
mkdir -p ./backups

# Full backup script
#!/bin/bash
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Stop services to ensure consistency
docker compose stop api

# Backup database
cp ./data/contract_comparator.db "$BACKUP_DIR/db_$DATE.db"

# Backup output
tar -czf "$BACKUP_DIR/output_$DATE.tar.gz" ./output/

# Restart services
docker compose start api

# Keep only last 30 days
find "$BACKUP_DIR" -name "db_*.db" -mtime +30 -delete
find "$BACKUP_DIR" -name "output_*.tar.gz" -mtime +30 -delete
```

### 4.2 Data Cleanup

The API provides a cleanup endpoint:

```bash
# Clean up tasks older than 48 hours
curl -X POST http://localhost:8080/api/v1/cleanup \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"max_age_hours": 48, "cleanup_audit_logs": true, "audit_max_age_days": 90}'
```

Automatic cleanup runs every hour (configurable via `DB_CLEANUP_INTERVAL`).

### 4.3 Data Retention Policy

| Data Type | Default Retention | Cleanup Mechanism |
|-----------|------------------|-------------------|
| Comparison tasks | 24 hours | Automatic / API |
| Audit logs | 90 days | Automatic / API |
| Output files | Manual | Manual cleanup |
| Temporary uploads | Immediate after processing | `_cleanup_temp_file` |

---

## 5. Security Operations

### 5.1 API Key Management

```bash
# Generate new key
curl -X POST http://localhost:8080/api/v1/auth/keys \
  -H "X-API-Key: admin-key" \
  -H "Content-Type: application/json" \
  -d '{"role": "analyst", "label": "user-zhang"}'

# List all keys
curl http://localhost:8080/api/v1/auth/keys \
  -H "X-API-Key: admin-key"

# Revoke a key
curl -X DELETE http://localhost:8080/api/v1/auth/keys/{key_id} \
  -H "X-API-Key: admin-key"

# Toggle key active/inactive
curl -X POST http://localhost:8080/api/v1/auth/keys/{key_id}/toggle \
  -H "X-API-Key: admin-key"
```

### 5.2 Key Rotation

- Rotate API keys every 90 days
- Generate new key before revoking old one to avoid service disruption
- Store the initial key output in a password manager
- Log all key generation/revocation events (audit trail)

### 5.3 Audit Log Review

```bash
# View recent audit logs
curl http://localhost:8080/api/v1/audit/logs?limit=50 \
  -H "X-API-Key: admin-key"

# Filter by event type
curl "http://localhost:8080/api/v1/audit/logs?event=comparison&limit=20" \
  -H "X-API-Key: admin-key"
```

---

## 6. Upgrade Procedure

### 6.1 In-Place Upgrade

```bash
# 1. Backup current data
./scripts/backup.sh

# 2. Pull latest code
git pull origin main

# 3. Rebuild images
docker compose build --no-cache api
docker compose build --no-cache streamlit

# 4. Restart services
docker compose up -d --force-recreate

# 5. Verify
curl http://localhost:8080/api/v1/health
```

### 6.2 Rollback

```bash
# Revert to previous version
git checkout v4.0.0
docker compose build
docker compose up -d --force-recreate
```

---

## 7. Capacity Planning

### 7.1 Resource Estimates

| Scenario | Users | Docs/Day | RAM | CPU | Disk |
|----------|-------|----------|-----|-----|------|
| Small team trial | 5 | 20 | 4 GB | 2 cores | 10 GB |
| Department | 20 | 100 | 8 GB | 4 cores | 50 GB |
| Enterprise | 50 | 500 | 16 GB | 8 cores | 200 GB |

### 7.2 OCR Performance

- Small PDF (5 pages): ~10-20 seconds
- Medium PDF (20 pages): ~40-80 seconds
- Large PDF (50 pages): ~100-200 seconds

Performance depends on:
- PDF image resolution (lower = faster but less accurate)
- OCR model selection
- Available CPU cores
- Concurrent task count

---

## 8. Common Issues

| Issue | Check | Solution |
|-------|-------|----------|
| Service won't start | `docker compose logs` | Check port conflicts, disk space |
| OCR fails on all documents | OCR model download | Check network, verify `ocr_engine.py` |
| Memory grows unbounded | Large concurrent uploads | Add `asyncio.Semaphore` limit |
| LLM not responding | Ollama service | Verify Ollama is running and model is pulled |
| Slow response times | Multiple concurrent tasks | Reduce batch size, add resources |
