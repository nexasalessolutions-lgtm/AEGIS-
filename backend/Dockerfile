FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown -R app:app /app /data
EXPOSE 8000
# Bind to Railway's configured public target port; Railway injects PORT=8080 by default.
# The generated public domain and healthcheck are explicitly configured for port 8000.
CMD ["sh", "-c", "mkdir -p /data && chown -R app:app /data && exec su -s /bin/sh app -c 'uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}'"]
