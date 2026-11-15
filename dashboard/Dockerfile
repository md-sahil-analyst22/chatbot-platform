# syntax=docker/dockerfile:1
# Bot Studio for the VPS (ADR-0008). Built by `docker compose -f infra/docker-compose.prod.yml up --build`.
# Stage 1 builds the static site; stage 2 is a tiny one-shot container that copies it into the
# folder host nginx serves (/var/www/saathi-studio, mounted at /out), then exits.

FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit
COPY . .
# Public API address baked into the bundle at build time (not a secret).
ARG VITE_API_BASE_URL
RUN test -n "$VITE_API_BASE_URL" || (echo "VITE_API_BASE_URL build arg is required" && exit 1)
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM alpine:3.22 AS publish
COPY --from=build /app/dist /site
# Replace the published files atomically enough for a small site: clear, then copy.
CMD ["sh", "-c", "find /out -mindepth 1 -delete && cp -R /site/. /out/ && echo 'Bot Studio published'"]
