FROM python:3.12-slim

WORKDIR /app

# 系統依賴(httpx/pandas 可能需要的基礎編譯工具,保持輕量)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models.py mock_data.py validation_suite.py datahub_client.py server.py ./
COPY schemas/ ./schemas/

# DataHub 連線資訊由環境變數注入,部署時透過 docker run -e 或 docker-compose env 提供,
# 不要寫死進 image 裡:
#   DATAHUB_GMS_URL
#   DATAHUB_TOKEN
ENV MCP_TRANSPORT=http
EXPOSE 8000

CMD ["python", "server.py"]
