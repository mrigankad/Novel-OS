# Running Novel OS in Docker

## Compose (two services)

```bash
cp .env.example .env              # add keys, or add connections in the studio later
docker compose up --build         # studio: http://localhost:3000, API: http://localhost:8000
```

- `api` runs uvicorn; `web` runs the Next standalone server and proxies `/api` to `http://api:8000`.
- The `novel-data` volume holds `/app/data` (SQLite database and media). Back it up, or use
  the studio's `.novelos.zip` export.
- Ports: `NOVEL_OS_WEB_PORT` and `NOVEL_OS_API_PORT` change the host side.
- Healthchecks: `GET /api/health` (api) and `GET /` (web); `web` waits for a healthy `api`.

### Postgres

```bash
NOVEL_OS_DATABASE_URL=postgresql+psycopg://novel:novel@postgres:5432/novel_os \
  docker compose --profile postgres up --build
```

`psycopg[binary]` is installed in the image. Migrations run on API startup. Start the `postgres`
service first (or rerun `up`) if the API starts before the database accepts connections.

### Research browser

```bash
WITH_BROWSER=1 docker compose build api     # installs Playwright + headless Chromium (~400 MB)
```

## One container

```bash
docker build -t novel-os .                  # target "all": uvicorn + node under scripts/supervise.py
docker run -p 3000:3000 -v novel-data:/app/data --env-file .env novel-os
```

## Notes

- The API URL the studio proxies to is fixed when the web image is built (Next resolves rewrites
  at build time); compose passes `NOVEL_OS_API_URL=http://api:8000` as a build arg.
- If you open the studio on a host other than `localhost:3000`, set `NOVEL_OS_CORS_ORIGINS`
  (only needed for direct browser calls to the API; the proxy is same-origin).
- The containers have no auth. Don't expose them to the internet without a reverse proxy that adds it.

## Access

The studio has no accounts. By default compose publishes both ports on `127.0.0.1`, so only this
computer can reach it. To write from another device, set a password and bind to all interfaces:

```
NOVEL_OS_PASSWORD=choose-one NOVEL_OS_BIND=0.0.0.0 docker compose up
```

Beta-reader links (`/read/...`) never need the password.
