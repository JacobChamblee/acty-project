FROM python:3.12-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python path so 'from ml.pipeline.x import y' resolves correctly
ENV PYTHONPATH=/app/backend

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8765

# Conditionally enable reload for development
CMD ["sh", "-c", "if [ \"$ACTY_RELOAD\" = \"false\" ]; then uvicorn backend.api.server:app --host 0.0.0.0 --port 8765; else uvicorn backend.api.server:app --host 0.0.0.0 --port 8765 --reload; fi"]
