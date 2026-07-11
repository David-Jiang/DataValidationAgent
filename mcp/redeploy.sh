#!/bin/bash
set -e

# ── 設定區 ──────────────────────────────────────────────
IMAGE_NAME="data-validation-agent-mcp"
CONTAINER_NAME="data-validation-agent-mcp"
PORT=8000
ENV_FILE=".env"
# ────────────────────────────────────────────────────────

echo "🔍 載入環境變數..."
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ 找不到 ${ENV_FILE},請先複製 .env.example 並填入正確的值:"
  echo "   cp .env.example .env"
  exit 1
fi

# 載入 .env(忽略空行與 # 開頭的註解)
export $(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | xargs)

if [ -z "$DATAHUB_GMS_URL" ]; then
  echo "❌ DATAHUB_GMS_URL 未設定,請檢查 .env"
  exit 1
fi
if [ -z "$DATAHUB_TOKEN" ]; then
  echo "❌ DATAHUB_TOKEN 未設定,請檢查 .env"
  exit 1
fi

echo "🛑 停止並移除舊 container(若存在)..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

echo "🔨 Build image..."
docker build -t "${IMAGE_NAME}:latest" .

echo "🚀 啟動新 container..."
docker run -d \
  -p "${PORT}:${PORT}" \
  -e DATAHUB_GMS_URL="$DATAHUB_GMS_URL" \
  -e DATAHUB_TOKEN="$DATAHUB_TOKEN" \
  -e MCP_TRANSPORT=http \
  -e MCP_PORT="$PORT" \
  --name "$CONTAINER_NAME" \
  "${IMAGE_NAME}:latest"

echo "✅ 完成!MCP Server 運行中 → http://localhost:${PORT}/mcp"
echo "📋 查看 log:  docker logs -f ${CONTAINER_NAME}"
