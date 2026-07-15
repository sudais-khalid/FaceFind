# ---- Build stage: compiles/installs dependencies with full toolchain ----
FROM python:3.11-slim AS build

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: slim image, no build tools, non-root user ----
FROM python:3.11-slim AS runtime

# libpq5 (runtime lib) is needed for asyncpg/psycopg; the rest are shared
# libraries mediapipe's opencv-contrib-python dependency needs merely to
# *import* cv2 on Linux (not to actually open a GUI window) - without them
# the app crashes on startup with "ImportError: libxcb.so.1: cannot open
# shared object file". libpq-dev/gcc (build tools) stay behind in the build
# stage.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libegl1 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY backend/app/ app/
COPY backend/alembic.ini alembic.ini

ENV PATH="/opt/venv/bin:$PATH"

# Pre-create the volume mount points so named volumes inherit appuser
# ownership - otherwise Docker creates them root-owned and the non-root
# runtime user cannot persist the FAISS index or thumbnail cache.
RUN useradd -m appuser \
    && mkdir -p /app/faiss_indexes /app/thumb_cache \
    && chown -R appuser:appuser /app /opt/venv
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
