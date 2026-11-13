# syntax=docker/dockerfile:1.7
#
# Novel OS 2. Targets:
#   api   FastAPI server only            (docker-compose.yml service "api")
#   web   Next.js standalone studio only (docker-compose.yml service "web")
#   all   both in one container under scripts/supervise.py (the default)
#
#   docker build -t novel-os .                                   # all-in-one
#   docker build --target api --build-arg WITH_BROWSER=1 .        # + Chromium for research
#
# NOVEL_OS_API_URL is baked into the web build: Next resolves rewrites at build time.
# The all-in-one image talks to 127.0.0.1:8000; compose builds web with http://api:8000.

ARG PYTHON_VERSION=3.13
ARG NODE_VERSION=22

# ---------------------------------------------------------------- web build
FROM node:${NODE_VERSION}-bookworm-slim AS web-build
WORKDIR /src/web
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY web/ ./
ARG NOVEL_OS_API_URL=http://127.0.0.1:8000
ENV NOVEL_OS_API_URL=${NOVEL_OS_API_URL}
RUN npx next build \
 && mkdir -p /out \
 && cp -r .next-prod/standalone/. /out/ \
 && mkdir -p /out/.next-prod \
 && cp -r .next-prod/static /out/.next-prod/static \
 && cp -r public /out/public

# ---------------------------------------------------------------- python base
FROM python:${PYTHON_VERSION}-slim-bookworm AS py
LABEL org.opencontainers.image.title="Novel OS" \
      org.opencontainers.image.description="AI novel-writing studio" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NOVEL_OS_DATA_DIR=/app/data
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt "psycopg[binary]>=3.1"
# Optional headless Chromium for the research swarm (adds ~400 MB).
ARG WITH_BROWSER=0
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$WITH_BROWSER" = "1" ]; then \
      pip install "playwright>=1.48" && playwright install --with-deps chromium; \
    fi
COPY alembic.ini ./
COPY migrations/ migrations/
COPY server/ server/
COPY core/ core/
COPY agents/ agents/
COPY templates/ templates/
COPY novel_os/ novel_os/
COPY scripts/ scripts/
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# ---------------------------------------------------------------- api
FROM py AS api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=4).status==200 else 1)"
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# ---------------------------------------------------------------- web
FROM node:${NODE_VERSION}-bookworm-slim AS web
WORKDIR /app/web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
LABEL org.opencontainers.image.licenses="AGPL-3.0-or-later"
COPY --from=web-build /out/ ./
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.status<500?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]

# ---------------------------------------------------------------- all-in-one
FROM py AS all
COPY --from=node:22-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=web-build /out/ /app/web/
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
EXPOSE 3000 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request,sys; [urllib.request.urlopen(u,timeout=4) for u in ('http://127.0.0.1:8000/api/health','http://127.0.0.1:3000/')]"
CMD ["python", "scripts/supervise.py"]
