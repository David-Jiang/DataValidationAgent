FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY models.py mock_data.py validation_suite.py datahub_client.py server.py ./
COPY schemas/ ./schemas/

EXPOSE 8000

CMD ["python", "server.py"]
