# Annex

[![Build & Push](https://github.com/TheSingularis/annex/actions/workflows/docker.yml/badge.svg)](https://github.com/TheSingularis/annex/actions/workflows/docker.yml)

Annex is a self-hosted middleware that takes unorganized ebook and audiobook directories and organizes them into your [Audiobookshelf](https://www.audiobookshelf.org/) library by resolving metadata and building a clean `Author/Title/` folder structure. Files are hardlinked rather than copied, so originals stay in place.

## Features

- Resolves metadata via [Audnexus](https://github.com/laxamentumtech/audnexus) (audiobooks) and OpenLibrary / Google Books (ebooks)
- Organizes files into `Author/Title/` library structure via hardlinks
- Polls for new downloads automatically on a configurable interval
- Queues low-confidence metadata matches for manual review via the UI
- Manual import for individual files or folders
- Notifies Audiobookshelf to scan after each import
- Single Docker container (Flask + Celery + Redis + React UI)

## Quick Start

```bash
cp backend/.env.example backend/.env
# edit backend/.env with your values
docker compose up -d
```

UI available at `http://<host>:5000`.

## Configuration

All configuration is via environment variables in `backend/.env`:

| Variable | Description | Default |
|---|---|---|
| `QBIT_HOST` | qBittorrent hostname | `localhost` |
| `QBIT_PORT` | qBittorrent port | `8080` |
| `QBIT_USERNAME` | qBittorrent username | `admin` |
| `QBIT_PASSWORD` | qBittorrent password | |
| `ABS_HOST` | Audiobookshelf URL | `http://localhost:13378` |
| `ABS_API_KEY` | Audiobookshelf API key | |
| `ABS_AUDIOBOOK_LIBRARY_ID` | ABS audiobook library ID | |
| `ABS_EBOOK_LIBRARY_ID` | ABS ebook library ID | |
| `AUDIOBOOK_LIBRARY_PATH` | Audiobook library root (inside container) | `/mnt/library/audiobooks` |
| `EBOOK_LIBRARY_PATH` | Ebook library root (inside container) | `/mnt/library/ebooks` |
| `CONFIDENCE_THRESHOLD` | Metadata match threshold (0–1) | `0.85` |
| `POLL_INTERVAL_SECONDS` | How often to check for new downloads | `60` |

## Unraid Setup

### docker-compose.yml volumes

```yaml
volumes:
  - /mnt/user/appdata/annex:/app/data
  - /mnt/user/downloads:/mnt/downloads:ro
  - /mnt/user/library:/mnt/library
```

**Important:** Your source directories and library must be on the same filesystem for hardlinks to work. If they are on different Unraid shares or pools, Annex will surface an error rather than silently copying.

### Auto-updates with Watchtower

Add Watchtower to your Unraid stack to automatically pull and redeploy new Annex releases:

```yaml
watchtower:
  image: containrrr/watchtower
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  environment:
    - WATCHTOWER_POLL_INTERVAL=3600
    - WATCHTOWER_CLEANUP=true
  restart: unless-stopped
```

## Development

```bash
# Start Redis
docker run -d --name redis-dev -p 6379:6379 redis:7-alpine

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your values
python run.py

# Celery (separate terminal)
celery -A celery_worker.celery worker --beat --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install && npm run dev
```

Frontend dev server: `http://localhost:5173` (proxies `/api` to Flask on `5000`)

## License

MIT
