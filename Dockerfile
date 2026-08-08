FROM ghcr.io/cirruslabs/flutter:stable AS web-build

WORKDIR /src/apps/mobile

COPY apps/mobile/pubspec.yaml apps/mobile/analysis_options.yaml ./
COPY apps/mobile/lib ./lib
COPY apps/mobile/assets ./assets

RUN flutter config --enable-web \
    && flutter create --platforms=web . \
    && flutter pub get \
    && flutter build web --release \
       --pwa-strategy=none \
       --dart-define=SIRISOS_API_URL=

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ghostscript \
        nginx \
        ocrmypdf \
        supervisor \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY apps/backend/app /app/app
COPY --from=web-build /src/apps/mobile/build/web /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/sirisos.conf

RUN mkdir -p /app/data/standards /app/logs /run/nginx

EXPOSE 6464

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=12 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6464/health', timeout=2).read()" || exit 1

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
