FROM node:24-alpine AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY webpack.config.js ./
COPY arcitek_ui/web ./arcitek_ui/web
RUN npm run build

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCITEK_HOST=0.0.0.0 \
    ARCITEK_PORT=8000 \
    ARCITEK_WORKERS=2 \
    ARCITEK_DATABASE=/app/data/arcitek.db

WORKDIR /app

RUN groupadd --system arcitek \
    && useradd --system --gid arcitek --home-dir /app arcitek \
    && mkdir -p /app/data \
    && chown arcitek:arcitek /app/data

COPY --chown=arcitek:arcitek arcitek_core ./arcitek_core
COPY --chown=arcitek:arcitek arcitek_ui/web/index.html arcitek_ui/web/styles.css ./arcitek_ui/web/
COPY --from=frontend --chown=arcitek:arcitek /build/arcitek_ui/web/dist ./arcitek_ui/web/dist

USER arcitek
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"]

CMD ["python", "-m", "arcitek_core.compute_service"]
