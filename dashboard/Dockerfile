# syntax=docker/dockerfile:1
# Bot Studio for the VPS (ADR-0008): built by `saathi up -d --build`, served behind Traefik.
# Stage 1 builds the static site; stage 2 serves it with non-root nginx on :8080.

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

FROM nginxinc/nginx-unprivileged:1.30-alpine AS serve
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
