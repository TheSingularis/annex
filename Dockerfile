# Stage 1: build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /ui
COPY frontend/package.json .
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Place built frontend where Flask can serve it
COPY --from=frontend-builder /ui/dist /app/frontend_dist

COPY supervisord.conf /etc/supervisor/conf.d/bookshelf.conf

EXPOSE 5000

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/bookshelf.conf"]
