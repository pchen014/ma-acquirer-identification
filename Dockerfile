# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python 3.14 Backend & Servicing
FROM python:3.14-slim AS final
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code, data, and CLI
COPY src/ ./src/
COPY cli.py .
COPY data/ ./data/

# Copy built frontend assets to FastAPI static folder
COPY --from=frontend-builder /app/frontend/dist ./src/static

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV GEMINI_MODEL="gemini-3.8-flash"
ENV DATABASE_PATH="/app/data/store/acquirer_profiles.db"
ENV PORT=8000

EXPOSE 8000

# Default command starts FastAPI servicing web app & static UI
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
