#!/bin/bash
# ============================================================
# 合同扫描件比对工具 - API 调用示例 (curl)
# Contract Document Comparator - API Examples (curl)
# ============================================================
# 使用前提: FastAPI 服务已启动 (默认端口 8080)
# Usage: ./curl_examples.sh

set -e

BASE_URL="${API_BASE_URL:-http://localhost:8080}"
API_KEY="${API_KEY:-}"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo " 合同比对工具 API 示例"
echo " Contract Comparator API Examples"
echo "=========================================="
echo ""

# ============================================================
# 1. 健康检查 (无需认证)
# ============================================================
echo -e "${GREEN}[1] 健康检查 / Health Check${NC}"
echo "GET $BASE_URL/health"
echo ""

curl -s "$BASE_URL/health" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/health"
echo ""
echo ""

# ============================================================
# 2. 生成 API Key (首次使用)
# ============================================================
echo -e "${GREEN}[2] 生成 API Key / Generate API Key${NC}"
echo "POST $BASE_URL/api/v1/auth/key"
echo ""

if [ -z "$API_KEY" ]; then
    echo "正在生成新的 API Key..."
    RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/auth/key" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "demo-key",
            "role": "analyst",
            "expires_in_days": 30
        }')
    
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
    
    # 提取 API Key (需要手动设置环境变量)
    echo ""
    echo -e "${YELLOW}请将生成的 API Key 设置到环境变量:${NC}"
    echo "  export API_KEY='your-api-key-here'"
    echo ""
else
    echo "已使用环境变量中的 API Key"
fi
echo ""

# ============================================================
# 3. 文档对比 (需要认证)
# ============================================================
echo -e "${GREEN}[3] 文档对比 / Document Comparison${NC}"
echo "POST $BASE_URL/api/v1/compare"
echo ""

# 注意: 请替换为实际的文件路径
WORD_FILE="${WORD_FILE:-./sample_contract.docx}"
PDF_FILE="${PDF_FILE:-./sample_scan.pdf}"

if [ -f "$WORD_FILE" ] && [ -f "$PDF_FILE" ]; then
    echo "上传文件进行对比..."
    curl -X POST "$BASE_URL/api/v1/compare" \
        -H "X-API-Key: $API_KEY" \
        -F "word_file=@$WORD_FILE" \
        -F "pdf_file=@$PDF_FILE" \
        -F "profile=general" \
        -F "use_llm=false" | python3 -m json.tool 2>/dev/null || true
else
    echo -e "${YELLOW}跳过: 未找到测试文件 ($WORD_FILE, $PDF_FILE)${NC}"
    echo "请设置环境变量 WORD_FILE 和 PDF_FILE 指向实际文件"
    echo ""
    echo "示例命令:"
    echo "  curl -X POST \"$BASE_URL/api/v1/compare\" \\"
    echo "    -H \"X-API-Key: \$API_KEY\" \\"
    echo "    -F \"word_file=@contract.docx\" \\"
    echo "    -F \"pdf_file=@scan.pdf\" \\"
    echo "    -F \"profile=general\""
fi
echo ""
echo ""

# ============================================================
# 4. 查询任务状态
# ============================================================
echo -e "${GREEN}[4] 查询任务状态 / Get Task Status${NC}"
echo "GET $BASE_URL/api/v1/compare/{task_id}"
echo ""

# 使用示例 task_id (实际使用时替换为对比返回的 task_id)
TASK_ID="${TASK_ID:-cli_demo_task}"
echo "示例: 查询任务 $TASK_ID 的状态"
echo ""
echo "curl -s \"$BASE_URL/api/v1/compare/$TASK_ID\" \\"
echo "    -H \"X-API-Key: \$API_KEY\""
echo ""

# ============================================================
# 5. 获取行业预设列表
# ============================================================
echo -e "${GREEN}[5] 获取行业预设 / List Industry Profiles${NC}"
echo "GET $BASE_URL/api/v1/profiles"
echo ""

curl -s "$BASE_URL/api/v1/profiles" \
    -H "X-API-Key: $API_KEY" | python3 -m json.tool 2>/dev/null || true
echo ""
echo ""

# ============================================================
# 6. 导出对比结果
# ============================================================
echo -e "${GREEN}[6] 导出对比结果 / Export Result${NC}"
echo "GET $BASE_URL/api/v1/export/{task_id}?format={format}"
echo ""

echo "支持的导出格式:"
echo "  - txt   : 纯文本报告"
echo "  - json  : 结构化 JSON"
echo "  - docx  : Word 红线标注"
echo "  - xlsx  : Excel 多 Sheet"
echo "  - pdf   : A4 格式报告"
echo "  - zip   : 全部格式打包"
echo ""
echo "示例命令:"
echo "  curl -s \"$BASE_URL/api/v1/export/$TASK_ID?format=json\" \\"
echo "    -H \"X-API-Key: \$API_KEY\" \\"
echo "    -o result.json"
echo ""

# ============================================================
# 7. 生成审计报告
# ============================================================
echo -e "${GREEN}[7] 系统指标 / System Metrics (Admin)${NC}"
echo "GET $BASE_URL/api/v1/metrics"
echo ""

curl -s "$BASE_URL/api/v1/metrics" \
    -H "X-API-Key: $API_KEY" | python3 -m json.tool 2>/dev/null || true
echo ""

echo "=========================================="
echo " 示例完成 / Examples Complete"
echo "=========================================="
