# ── Build stage ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_URL is baked into the bundle at build time.
ARG VITE_API_URL="/api"
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# ── Serve stage ──────────────────────────────────────────────────────────────
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
