# ============================================================
# Stage 1 — Builder
# ============================================================
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2 — Runtime
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# Runtime OS packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Create non-root user (Cloud Run best practice)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Environment
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Cloud Run uses dynamic $PORT — default = 8080
EXPOSE 8080
ENV PORT=8080
ENV ENVIRONMENT=production

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import os,urllib.request; port=os.getenv('PORT','8080'); urllib.request.urlopen('http://localhost:'+port+'/health')" || exit 1

# ============================================================
# ✅ Correct Cloud Run startup command
# Uses sh -c so $PORT is expanded correctly
# ============================================================
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 75 --access-log"]