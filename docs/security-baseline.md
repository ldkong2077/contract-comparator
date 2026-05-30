# Security Baseline / 安全基线

## Overview / 概述

This document defines the security baseline for Contract Comparator enterprise
trial deployments. It covers authentication, network security, data protection,
logging, and operational security measures.

---

## 1. Authentication & Access Control / 认证与访问控制

### 1.1 API Key Authentication

| Requirement | Standard | Notes |
|-------------|----------|-------|
| Key storage | HMAC-SHA256 hash | Plaintext never stored |
| Key transport | HTTP Header (`X-API-Key`) only | Query parameter prohibited |
| Key generation | Cryptographically random | 32-byte random hex |
| Default key | Disabled in production | Must generate explicitly |
| Key rotation | Every 90 days | Automated via API |

### 1.2 Role-Based Access Control (RBAC)

| Role | Permissions | Typical User |
|------|-------------|-------------|
| **Admin** | Full access: compare, export, manage keys, manage profiles, view audit | System administrator |
| **Analyst** | Compare, export, manage profiles | Legal/finance analyst |
| **Viewer** | Export only (view results) | Auditor, reviewer |

### 1.3 Rate Limiting

| Parameter | Default | Production Recommended |
|-----------|---------|----------------------|
| Requests per minute | 30 | 60 (per user) |
| Burst | 5 | 10 |
| Client identification | Key ID + role | Same (IP-based for unauthenticated) |

---

## 2. Network Security / 网络安全

### 2.1 Deployment Boundary

- **Recommended**: Internal network or VPN only
- **Not recommended**: Direct public internet exposure
- **Production path**: Deploy behind reverse proxy with TLS

### 2.2 CORS Configuration

```
Allowed origins: localhost, 127.0.0.1 (development only)
Production: Restrict to specific internal domain(s)
```

### 2.3 TLS / HTTPS

| Environment | TLS Requirement |
|-------------|-----------------|
| Local development | Not required |
| Internal network | Recommended |
| VPN access | Recommended |
| Public internet | **Mandatory** |

### 2.4 Ports

| Port | Service | Bound To | Notes |
|------|---------|----------|-------|
| 8501 | Streamlit UI | 0.0.0.0 | Internal use only |
| 8080 | FastAPI API | 0.0.0.0 | Internal use only |
| 11434 | Ollama (optional) | 0.0.0.0 | Internal use only |

---

## 3. File Upload Security / 文件上传安全

### 3.1 Validation Chain

| Check | Description | Implementation |
|-------|-------------|----------------|
| Extension whitelist | Only allow `.pdf`, `.docx`, `.xlsx`, image formats | `_save_upload_file` |
| Magic number verification | Verify file header matches extension | `FileUploadValidator.validate_file_type` |
| File size limit | Max 50 MB | `MAX_UPLOAD_BYTES` |
| File integrity | ZIP directory validation for DOCX/XLSX | `FileUploadValidator.validate_file_integrity` |

### 3.2 Upload Restrictions

- Maximum file size: 50 MB (configurable via `MAX_FILE_SIZE_MB`)
- Maximum batch pairs: 10 (configurable via `MAX_BATCH_PAIRS`)
- Temporary files: Automatically cleaned after processing
- No executable file types allowed

---

## 4. Data Protection / 数据保护

### 4.1 Sensitive Data Masking

| Data Type | Mask Pattern | Example |
|-----------|-------------|---------|
| Phone numbers | `***PHONE***` | 138****1234 → `***PHONE***` |
| Email addresses | `***EMAIL***` | user@example.com → `***EMAIL***` |
| ID card numbers | `***ID_CARD***` | 350101********1234 → `***ID_CARD***` |
| Bank accounts | `***BANK_ACCOUNT***` | 6217**********7890 → `***BANK_ACCOUNT***` |
| Company seals | `***SEAL***` | B621JE12345 → `***SEAL***` |

### 4.2 Database Encryption

- SQLite database supports Fernet encryption for sensitive fields
- `cryptography` is a **required** dependency (not optional)
- Encryption key management: stored separately from database

### 4.3 Temporary File Security

- All temporary files created in restricted-access directories (0700)
- Windows: icacls restricts to current user only
- Files cleaned immediately after processing
- Path traversal protection via `validate_path_safe`

### 4.4 LLM Data Handling

| LLM Type | Data Flow | Security Requirement |
|----------|-----------|---------------------|
| **Ollama** (local) | All data stays on machine | None additional |
| **Claude API** (cloud) | Data sent to Anthropic | Requires customer authorization, data processing agreement |

---

## 5. Logging & Auditing / 日志与审计

### 5.1 Audit Logging

| Event Type | Logged Fields | Retention |
|------------|--------------|-----------|
| File access | user_id, file_name, action | 90 days |
| Comparison | user_id, word_file, pdf_file, result_summary | 90 days |
| Export | user_id, format, file_path | 90 days |
| Error | user_id, error_type, details | 90 days |
| API Key operations | user_id, key_id, event | 90 days |

### 5.2 Log Formats

- Audit logs: JSON Lines format, `./output/audit.log`
- Application logs: Structured text via `logging` module
- Log rotation: 10 MB per file, 5 backup files

### 5.3 What NOT to Log

- Full API Keys (masked only: first 4 + last 4 characters)
- Raw contract text content (unless explicitly configured)
- User passwords or authentication secrets

---

## 6. Error Handling / 错误处理

### 6.1 Production Error Response Format

```json
{
  "detail": "服务器内部错误，请稍后重试。",
  "error_code": 500,
  "request_id": "a1b2c3d4e5f6",
  "timestamp": "2026-01-15T14:30:00Z"
}
```

### 6.2 Rules

- **Never** return `str(exc)` or `traceback` to the client
- **Always** log full error details internally
- **Always** include `request_id` for error correlation
- **Never** expose internal paths, configuration, or stack traces

---

## 7. Container Security / 容器安全

### 7.1 Dockerfile Security

- **Non-root user**: Application runs as `app` user (not root)
- **Minimal base image**: `python:3.11-slim`
- **No sensitive data** in image layers
- **Healthcheck**: Configured for both services

### 7.2 Docker Compose Security

- `restart: unless-stopped` for high availability
- Read-only mounts for configuration (`:ro`)
- Network isolation via Docker internal networks
- Resource limits recommended for production

---

## 8. Compliance Checklist

- [ ] Authentication enabled (`AUTH_ENABLED=true`)
- [ ] Default admin key NOT printed to stdout
- [ ] Rate limiting enabled
- [ ] CORS restricted to known origins
- [ ] File upload magic number validation active
- [ ] Sensitive data masking enabled
- [ ] Audit logging active
- [ ] Error responses do not include `str(exc)`
- [ ] `cryptography` dependency installed
- [ ] API Key query parameter transport disabled
- [ ] Docker containers run as non-root user
- [ ] Temporary files properly cleaned up
- [ ] Deployed behind reverse proxy with TLS (production)
- [ ] Access restricted to internal network / VPN
- [ ] Backup strategy documented
