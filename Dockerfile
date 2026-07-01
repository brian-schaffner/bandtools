# Band Tools — multi-component monorepo (Setlist Loader + Gig Flyers + hub UI)
FROM node:20-bookworm-slim AS frontend-build

WORKDIR /app/setloader/setlist-helper
COPY setloader/setlist-helper/package.json setloader/setlist-helper/package-lock.json ./
RUN npm ci

COPY setloader/setlist-helper/ ./
ENV NEXT_PUBLIC_API_URL=/api
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    gcc \
    poppler-utils \
    tesseract-ocr \
    fonts-dejavu-core \
    fonts-liberation2 \
    fontconfig \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f -v \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app

# Separate venvs keep dependency sets isolated
COPY setloader/requirements.txt /tmp/setloader-requirements.txt
RUN python3 -m venv /opt/setloader-venv \
    && /opt/setloader-venv/bin/pip install --no-cache-dir -r /tmp/setloader-requirements.txt

COPY gig-flyers/requirements.txt /tmp/flyers-requirements.txt
RUN python3 -m venv /opt/flyers-venv \
    && /opt/flyers-venv/bin/pip install --no-cache-dir -r /tmp/flyers-requirements.txt

COPY setloader/ ./setloader/
COPY gig-flyers/ ./gig-flyers/

# Next.js standalone output
COPY --from=frontend-build /app/setloader/setlist-helper/.next/standalone ./setlist-helper/.next/standalone/
COPY --from=frontend-build /app/setloader/setlist-helper/.next/static ./setlist-helper/.next/static/
COPY --from=frontend-build /app/setloader/setlist-helper/public ./setlist-helper/.next/standalone/public/

COPY nginx.conf /app/nginx.conf
COPY supervisord/bandtools.conf /etc/supervisor/conf.d/bandtools.conf
COPY scripts/fly-entrypoint.sh /app/scripts/fly-entrypoint.sh
RUN chmod +x /app/scripts/fly-entrypoint.sh

ENV PORT=8090
ENV BACKEND_PORT=8002
ENV FRONTEND_PORT=3000
ENV FLYERS_PORT=8080
ENV DATA_DIR=/data
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8090

ENTRYPOINT ["/app/scripts/fly-entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/bandtools.conf"]
