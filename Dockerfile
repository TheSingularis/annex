# Stage 1: build React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /ui
COPY frontend/package.json .
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: runtime
FROM python:3.12-slim

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

# Debian's `calibre` apt package hard-depends on the full GUI stack (Qt6
# WebEngine -- an embedded Chromium -- plus scipy/numpy/sympy, ~600MB we
# never use for headless azw3/mobi->epub conversion). The upstream installer
# bundles its own self-contained Qt/Python runtime and needs only a handful
# of base X/graphics shared libs to run ebook-convert headlessly instead,
# cutting the image by ~400MB (measured: 1.55GB -> 1.14GB). The remaining
# size is the self-contained Calibre bundle itself plus Mesa/LLVM (needed by
# any headless Qt6 GUI toolkit for software GL rendering) -- both structural,
# not further reducible without dropping Calibre. wget/xz-utils are
# build-only and removed afterward.
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    supervisor \
    wget \
    xz-utils \
    libfreetype6 \
    libfontconfig1 \
    libxrender1 \
    libxext6 \
    libsm6 \
    libice6 \
    libglib2.0-0 \
    libdbus-1-3 \
    libx11-6 \
    libxkbcommon0 \
    libgl1 \
    libegl1 \
    libopengl0 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libnss3 \
    && wget -q -O /tmp/calibre-installer.sh https://download.calibre-ebook.com/linux-installer.sh \
    && sh /tmp/calibre-installer.sh install_dir=/opt isolated=y \
    && apt-get purge -y --auto-remove wget xz-utils \
    && rm -rf /tmp/calibre-installer.sh /tmp/calibre-installer-cache /var/lib/apt/lists/*

ENV PATH="/opt/calibre:${PATH}"

# ebook-convert is a Qt app; force the offscreen platform plugin so it runs
# headless without an X server (see app/ebook_convert.py).
ENV QT_QPA_PLATFORM=offscreen

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Place built frontend where Flask can serve it
COPY --from=frontend-builder /ui/dist /app/frontend_dist

COPY supervisord.conf /etc/supervisor/conf.d/bookshelf.conf

EXPOSE 5000

CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/bookshelf.conf"]
