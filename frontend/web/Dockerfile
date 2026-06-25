FROM node:22-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_USE_MOCK=false
ARG VITE_API_TOKEN=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_API_TOKEN=$VITE_API_TOKEN

COPY frontend/web/package.json frontend/web/package-lock.json ./
RUN npm ci

COPY frontend/web ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY frontend/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080
