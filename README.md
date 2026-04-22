## Checkers Deployment (Docker)

Main deployment files live in this backend repository.
Run all commands from `Checkers-API/`.

### Prerequisites

1. Docker Desktop (or Docker Engine + Compose plugin)
2. A `.env` file in `Checkers-API/`

You can start from:

```bash
cp .env.example .env
```

Then set a strong `DJANGO_SECRET_KEY`.

## Option A: Full stack from local backend + local frontend source

Use this when both repositories are present side-by-side:

- `../Checkers-React`
- `./Checkers-API`

Start:

```bash
docker compose up --build -d
```

Open app:

- Frontend: `http://localhost:8080`
- API (through frontend proxy): `http://localhost:8080/api/`

Stop:

```bash
docker compose down
```

## Option B: Clone only backend and use prebuilt frontend image

When you only cloned this backend repo, run with `docker-compose.backend-only.yml`.

1. Publish/build frontend image separately (example tag: `ghcr.io/your-org/checkers-frontend:latest`).
2. Export image name:

```bash
export FRONTEND_IMAGE=ghcr.io/your-org/checkers-frontend:latest
```

PowerShell:

```powershell
$env:FRONTEND_IMAGE="ghcr.io/your-org/checkers-frontend:latest"
```

3. Start:

```bash
docker compose -f docker-compose.backend-only.yml up --build -d
```

Stop:

```bash
docker compose -f docker-compose.backend-only.yml down
```

## Notes

- Backend DB is persisted in Docker volume `backend_data`.
- Frontend container proxies `/api/*` to `backend:8000`, so browser uses one origin.
- Backend runs migrations automatically at container startup.
