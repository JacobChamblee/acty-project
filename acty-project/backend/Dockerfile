FROM python:3.12-slim

WORKDIR /app

# System deps for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

EXPOSE 8765

CMD ["uvicorn", "backend.api.server:app", "--host", "0.0.0.0", "--port", "8765", "--reload"]
