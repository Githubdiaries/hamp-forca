FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY ml/ ./ml/
COPY config/ ./config/
COPY tests/ ./tests/
COPY pytest.ini .
COPY requirements-dev.txt .

ENV PYTHONPATH=/app
ENV MODEL_DIR=/models

RUN mkdir -p /models

EXPOSE 8000

CMD ["python", "-m", "src.main"]
