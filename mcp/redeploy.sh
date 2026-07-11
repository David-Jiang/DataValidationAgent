#!/bin/bash
set -e

# ── 設定區 ──────────────────────────────────────────────
IMAGE_NAME="dva-mcp"
CONTAINER_NAME="dva-mcp"
ENV_FILE=".env"
# ────────────────────────────────────────────────────────


export $(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | xargs)

if [ -z "$DATAHUB_HOST" ]; then
  echo "❌ DATAHUB_HOST 未設定,請檢查 .env"
  exit 1
fi
if [ -z "$DATAHUB_TOKEN" ]; then
  echo "❌ DATAHUB_TOKEN 未設定,請檢查 .env"
  exit 1
fi
if [ -z "$PORT" ]; then
  echo "❌ PORT 未設定,請檢查 .env"
  exit 1
fi

docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm   "$CONTAINER_NAME" 2>/dev/null || true

docker build -t "${IMAGE_NAME}:latest" .

docker run -d \
  -p "${PORT}:8000" \
  -e DATAHUB_HOST="$DATAHUB_HOST" \
  -e DATAHUB_TOKEN="$DATAHUB_TOKEN" \
  --name "$CONTAINER_NAME" \
  "${IMAGE_NAME}:latest"

echo "✅ 完成!MCP Server 運行中 → http://localhost:${PORT}/mcp"
echo "📋 查看 log:  docker logs -f ${CONTAINER_NAME}"
