# Annex

[![Build & Push](https://github.com/TheSingularis/annex/actions/workflows/docker.yml/badge.svg)](https://github.com/TheSingularis/annex/actions/workflows/docker.yml)

Annex watches directories of unorganized ebooks and audiobooks and automatically organizes them into a clean `Author/Title/` library structure using resolved metadata. Files are hardlinked rather than copied, so originals stay in place.

## Features

- Watches configurable directories for new audiobook and ebook files
- Resolves metadata via [Audnexus](https://github.com/laxamentumtech/audnexus) (audiobooks) and OpenLibrary / Google Books (ebooks)
- Organizes files into `Author/Title/` structure via hardlinks — originals untouched
- Queues low-confidence matches for manual review via the UI
- Manual import for individual files or folders
- Single Docker container — no external dependencies

## Quick Start

```bash
cp backend/.env.example backend/.env
# edit backend/.env with your paths
docker compose up -d
```

UI available at `http://<host>:5000`.

## Configuration

### Your setup

These tell Annex where your files live. Set these to match your directory structure.

| Variable | Description |
|---|---|
| `AUDIOBOOK_WATCH_PATH` | Directory to watch for new audiobooks (inside container) |
| `EBOOK_WATCH_PATH` | Directory to watch for new ebooks (inside container) |
| `AUDIOBOOK_LIBRARY_PATH` | Where organized audiobooks will be placed (inside container) |
| `EBOOK_LIBRARY_PATH` | Where organized ebooks will be placed (inside container) |

### App settings

Tuneable but work out of the box.

| Variable | Description | Default |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | Metadata match score (0–1). Below this, item is queued for manual review | `0.85` |
| `POLL_INTERVAL_SECONDS` | How often to scan watch directories | `60` |

### Optional — Audiobookshelf integration

When configured, Annex triggers an ABS library scan after each successful import.

| Variable | Description |
|---|---|
| `ABS_HOST` | Audiobookshelf URL (e.g. `http://192.168.1.100:13378`) |
| `ABS_API_KEY` | Audiobookshelf API key |
| `ABS_AUDIOBOOK_LIBRARY_ID` | ABS audiobook library ID |
| `ABS_EBOOK_LIBRARY_ID` | ABS ebook library ID |

## Unraid Setup

```yaml
volumes:
  - /mnt/user/appdata/annex:/app/data
  - /mnt/user/downloads:/mnt/downloads:ro
  - /mnt/user/library:/mnt/library
```

**Important:** Watch directories and library destinations must be on the same filesystem for hardlinks to work.

## Development

```bash
# Start Redis
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py

# Celery (separate terminal)
celery -A celery_worker.celery worker --beat --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install && npm run dev
```

Frontend: `http://localhost:5173` — proxies `/api` to Flask on port `5000`.

## License

MIT
