FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for document parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules and backend
COPY core/ ./core/
COPY ai/ ./ai/
COPY backend/ ./backend/

WORKDIR /app/backend

EXPOSE 5001

CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "300", "run:app"]
