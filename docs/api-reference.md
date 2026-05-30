# API Reference / API 参考文档

**Base URL:** `http://localhost:8080/api/v1`

**Authentication:** All endpoints (except `/health` and `/docs`) require `X-API-Key` header.

---

## 1. Compare / 对比

### POST `/compare`

Execute a document comparison task.

**Request:**

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| `word_file` | File | Form | Yes | Original Word document (.docx) |
| `pdf_file` | File | Form | Yes | Scanned PDF/image (.pdf, .jpg, .png) |
| `profile` | String | Form | No | Industry preset (`general`, `construction`, `leasing`, `procurement`, `labor`) |
| `use_llm` | Bool | Form | No | Enable LLM assistance (`true`/`false`) |
| `model` | String | Form | No | Ollama model name (default: `qwen3.5-0.8b`) |

**Response 201:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "created_at": "2026-05-25T10:30:00Z"
}
```

### GET `/compare/{task_id}`

Get comparison results by task ID.

**Response 200:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2026-05-25T10:30:00Z",
  "completed_at": "2026-05-25T10:30:45Z",
  "result": {
    "summary": {
      "total_fields": 24,
      "fields_match": 20,
      "fields_differ": 3,
      "low_confidence": 1,
      "risk_level": "medium"
    },
    "field_diffs": [
      {
        "field_name": "合同金额",
        "status": "differ",
        "word_value": "150000.00",
        "pdf_value": "160000.00",
        "confidence": 0.95,
        "risk": "high"
      }
    ],
    "full_text_diff": {
      "chunks": [
        {
          "type": "equal",
          "text": "甲方：...",
          "risk": "none"
        },
        {
          "type": "delete",
          "text": "原条款内容",
          "risk": "medium"
        },
        {
          "type": "insert",
          "text": "新条款内容",
          "risk": "medium"
        }
      ]
    }
  }
}
```

### GET `/compare/{task_id}/status`

Poll task progress.

**Response 200:**

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 65,
  "stage": "ocr_recognition"
}
```

### POST `/compare/batch`

Execute multiple comparisons in batch.

**Request:**

| Parameter | Type | Location | Required | Description |
|-----------|------|----------|----------|-------------|
| `files` | File[] | Form | Yes | Multiple (word, pdf) file pairs |
| `profile` | String | Form | No | Industry preset |

**Response 201:**

```json
{
  "batch_id": "batch-001",
  "tasks": ["task-id-1", "task-id-2"],
  "status": "processing"
}
```

### DELETE `/compare/{task_id}`

Delete a comparison task and its results.

**Response 204:** No content

---

## 2. Export / 导出

### GET `/export/{task_id}`

Export comparison results in specified format.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `format` | String | Yes | Export format: `txt`, `json`, `docx`, `xlsx`, `pdf`, `zip` |

**Response:** File download with appropriate Content-Type header.

---

## 3. Profiles / 行业预设

### GET `/profiles`

List all available industry presets.

**Response 200:**

```json
{
  "profiles": [
    {
      "name": "general",
      "display_name": "通用",
      "description": "标准合同比对配置"
    },
    {
      "name": "construction",
      "display_name": "建筑行业",
      "description": "工程合同、工程量清单比对"
    }
  ],
  "active_profile": "general"
}
```

### POST `/profiles`

Create a custom profile.

**Request:**

```json
{
  "name": "my-custom-profile",
  "display_name": "自定义配置",
  "description": "我的自定义比对配置",
  "field_patterns": {
    "amount": "^\\d+(\\.\\d{1,2})?$",
    "date": "\\d{4}-\\d{2}-\\d{2}"
  },
  "tolerance": {
    "number": 0.01,
    "date_days": 0
  }
}
```

### GET|PUT|DELETE `/profiles/{name}`

Get, update, or delete a specific profile.

---

## 4. Authentication / 认证

### POST `/auth/key`

Generate a new API key (Admin only).

**Request:**
```json
{
  "role": "Analyst",
  "expires_in_days": 30
}
```

**Response 201:**

```json
{
  "key_id": "key-001",
  "api_key": "sk-xxxx...",
  "role": "Analyst",
  "created_at": "2026-05-25T10:00:00Z",
  "expires_at": "2026-06-24T10:00:00Z"
}
```

### POST `/auth/verify`

Verify an API key's validity.

### GET `/auth/keys`

List all active API keys (Admin only).

### DELETE `/auth/key/{key_id}`

Revoke an API key (Admin only).

---

## 5. System / 系统

### GET `/health`

Health check endpoint. No authentication required.

**Response 200:**

```json
{
  "status": "healthy",
  "version": "4.0.0",
  "uptime_seconds": 3600,
  "ollama_connected": true,
  "database_connected": true
}
```

### GET `/metrics`

System metrics (Admin only).

**Response 200:**

```json
{
  "total_comparisons": 150,
  "active_tasks": 3,
  "average_processing_time_ms": 4500,
  "cache_hit_rate": 0.85,
  "error_rate": 0.02
}
```

---

## Error Codes / 错误码

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | `INVALID_REQUEST` | Missing or invalid parameters |
| 401 | `UNAUTHORIZED` | Missing or invalid API key |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Task or resource not found |
| 409 | `CONFLICT` | Resource already exists |
| 413 | `FILE_TOO_LARGE` | File exceeds size limit |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Invalid file format |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

**Error Response Format:**

```json
{
  "error": {
    "code": "RATE_LIMITED",
    "message": "Rate limit exceeded. Try again in 30 seconds.",
    "retry_after": 30
  }
}
```

---

## Date Formats / 日期格式

All timestamps use ISO 8601 format: `YYYY-MM-DDTHH:mm:ssZ`
