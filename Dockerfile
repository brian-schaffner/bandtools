# Band Tools — multi-component monorepo (Setlist Loader + Gig Flyer Studio + hub UI)
ARG BANDTOOLS_GIT_SHA=unknown
ARG BANDTOOLS_BUILD_NUMBER=dev
ARG BANDTOOLS_BUILD_TIME=
ARG BANDTOOLS_DEPLOY_ENV=local
ARG BANDTOOLS_BUILD_LABEL=dev-unknown

FROM node:20-bookworm-slim AS frontend-build

ARG BANDTOOLS_BUILD_LABEL
ARG BANDTOOLS_BUILD_TIME
ARG BANDTOOLS_DEPLOY_ENV
WORKDIR /app/setloader/setlist-helper
COPY setloader/setlist-helper/package.json setloader/setlist-helper/package-lock.json ./
RUN npm ci

COPY setloader/setlist-helper/ ./
ARG NEXT_PUBLIC_API_SECRET=change-me
ENV NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_SECRET=${NEXT_PUBLIC_API_SECRET}
ENV NEXT_PUBLIC_BANDTOOLS_BUILD_LABEL=${BANDTOOLS_BUILD_LABEL}
ENV NEXT_PUBLIC_BANDTOOLS_BUILT_AT=${BANDTOOLS_BUILD_TIME}
ENV NEXT_PUBLIC_BANDTOOLS_DEPLOY_ENV=${BANDTOOLS_DEPLOY_ENV}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS flyer-forge-build

WORKDIR /app/setloader/flyer-forge
COPY setloader/flyer-forge/package.json setloader/flyer-forge/package-lock.json ./
RUN npm ci

COPY setloader/flyer-forge/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_BASE_PATH=/flyer-forge
ENV AUTH_PROVIDER=google
RUN npm run build

FROM python:3.12-bookworm

ARG BANDTOOLS_GIT_SHA
ARG BANDTOOLS_BUILD_NUMBER
ARG BANDTOOLS_BUILD_TIME
ARG BANDTOOLS_DEPLOY_ENV
ARG BANDTOOLS_BUILD_LABEL

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
    ffmpeg \
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

COPY show-recap/requirements.txt /tmp/show-recap-requirements.txt
RUN python3 -m venv /opt/show-recap-venv \
    && /opt/show-recap-venv/bin/pip install --no-cache-dir -r /tmp/show-recap-requirements.txt

COPY setloader/ ./setloader/
COPY gig-flyers/ ./gig-flyers/
COPY show-recap/ ./show-recap/

# Next.js standalone output (static assets must live under standalone/.next/static)
COPY --from=frontend-build /app/setloader/setlist-helper/.next/standalone ./setlist-helper/.next/standalone/
COPY --from=frontend-build /app/setloader/setlist-helper/.next/static ./setlist-helper/.next/standalone/.next/static/
COPY --from=frontend-build /app/setloader/setlist-helper/public ./setlist-helper/.next/standalone/public/

# Gig Flyer Studio (Flyer Forge) — embedded at /flyer-forge
COPY --from=flyer-forge-build /app/setloader/flyer-forge/.next/standalone ./flyer-forge/.next/standalone/
COPY --from=flyer-forge-build /app/setloader/flyer-forge/.next/static ./flyer-forge/.next/standalone/.next/static/
COPY --from=flyer-forge-build /app/setloader/flyer-forge/public ./flyer-forge/.next/standalone/public/
COPY --from=flyer-forge-build /app/setloader/flyer-forge/migrations ./flyer-forge/.next/standalone/migrations
COPY --from=flyer-forge-build /app/setloader/flyer-forge/scripts ./flyer-forge/.next/standalone/scripts
COPY --from=flyer-forge-build /app/setloader/flyer-forge/node_modules/@electric-sql/pglite ./flyer-forge/.next/standalone/node_modules/@electric-sql/pglite
COPY --from=flyer-forge-build /app/setloader/flyer-forge/node_modules/pg ./flyer-forge/.next/standalone/node_modules/pg

COPY nginx.conf /app/nginx.conf
COPY supervisord/bandtools.conf /etc/supervisor/conf.d/bandtools.conf
COPY scripts/fly-entrypoint.sh /app/scripts/fly-entrypoint.sh
COPY scripts/write_build_info.py /app/scripts/write_build_info.py
RUN chmod +x /app/scripts/fly-entrypoint.sh

ENV BANDTOOLS_GIT_SHA=${BANDTOOLS_GIT_SHA} \
    BANDTOOLS_BUILD_NUMBER=${BANDTOOLS_BUILD_NUMBER} \
    BANDTOOLS_BUILD_TIME=${BANDTOOLS_BUILD_TIME} \
    BANDTOOLS_DEPLOY_ENV=${BANDTOOLS_DEPLOY_ENV} \
    BANDTOOLS_BUILD_LABEL=${BANDTOOLS_BUILD_LABEL}
RUN python3 /app/scripts/write_build_info.py

ENV PORT=8090
ENV BACKEND_PORT=8002
ENV FRONTEND_PORT=3000
ENV FLYER_FORGE_PORT=3010
ENV DATA_DIR=/data
ENV NODE_ENV=production
ENV PYTHONUNBUFFERED=1

EXPOSE 8090

ENTRYPOINT ["/app/scripts/fly-entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/bandtools.conf"]
