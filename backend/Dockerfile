FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Render (and any other PaaS with an ephemeral filesystem) injects PORT at
# runtime and expects the process to bind to it; 8000 is only the local
# fallback. UPLOAD_DIR itself is created by app/storage.py on import.
RUN useradd -m appuser \
    && mkdir -p /app/uploads/licenses \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
