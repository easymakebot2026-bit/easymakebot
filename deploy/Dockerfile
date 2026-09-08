# Build context is the REPO ROOT (see docker-compose.bot.yml: build.context: ..).
#
#   Stage 1 builds the visual-flow-builder Mini App (webapp/) so the server
#   never needs Node/npm installed.
#   Stage 2 is the Python runtime that actually runs `python -m bot.main`
#   (Telegram long-polling + the aiohttp Mini App server on WEBAPP_PORT).

# ---- stage 1: Mini App frontend ----
FROM node:22-slim AS webapp
WORKDIR /webapp
COPY webapp/package.json webapp/package-lock.json ./
RUN npm ci
COPY webapp/ ./
RUN npm run build          # -> /webapp/dist

# ---- stage 2: Python runtime ----
FROM python:3.13-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# libjpeg/zlib: reportlab needs them at runtime for image embedding in the
# generated shop invoices.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot/ ./bot/
# bot/webapp_server.py resolves STATIC_DIR as <repo>/webapp/dist
COPY --from=webapp /webapp/dist ./webapp/dist

RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser

CMD ["python", "-m", "bot.main"]
