# Stage 1: build Vue 3 frontend
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY apps/frontend/package*.json ./
RUN npm ci
COPY apps/frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend/app/ app/
COPY apps/backend/db/ db/
COPY apps/backend/alembic/ alembic/
COPY apps/backend/alembic.ini .
COPY apps/backend/run_watcher.py apps/backend/run_api.py apps/backend/run_scan.py ./
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-u", "run_api.py"]
