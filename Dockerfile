# Multi-stage Dockerfile for MediaHunt
# Stage 1: build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile || yarn install
COPY frontend/ ./
# The standalone Docker image serves frontend from FastAPI on a single port.
# The build will hit the same origin, so REACT_APP_BACKEND_URL is set to "".
ENV REACT_APP_BACKEND_URL=""
RUN yarn build

# Stage 2: backend + serve static
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5556 \
    MEDIAHUNT_DATA_DIR=/app/data
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend/ ./backend/
COPY --from=frontend-builder /build/build ./frontend/build
COPY docker/start.sh ./start.sh
RUN chmod +x ./start.sh
RUN mkdir -p ${MEDIAHUNT_DATA_DIR}

EXPOSE 5556
VOLUME ["/app/data"]
CMD ["./start.sh"]
