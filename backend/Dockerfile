FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ARG INSTALL_RAG=false
COPY backend/requirements-rag.txt .
RUN if [ "$INSTALL_RAG" = "true" ]; then pip install --no-cache-dir -r requirements-rag.txt; fi
COPY backend/app ./backend/app
COPY backend/migrations ./backend/migrations
COPY backend/alembic.ini ./backend/alembic.ini
COPY agent ./agent
COPY scripts ./scripts
RUN groupadd -g 10001 app && useradd -u 10001 -g app -m app && mkdir -p /app/backend/data/reports && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
