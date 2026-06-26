# Stage 1: Build Next.js frontend (static export)
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Output: /app/frontend/out/ (requires output: 'export' in next.config.ts)

# Stage 2: Production image (Python 3.12 + uv)
FROM python:3.12-slim AS production
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install Python dependencies from lockfile (no dev deps)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Copy backend source
COPY backend/ ./

# Copy frontend static export
COPY --from=frontend-builder /app/frontend/out ./static

# Create db directory for SQLite volume mount
RUN mkdir -p /app/db

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
