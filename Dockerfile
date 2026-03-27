# Use Python 3.11 slim
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy app files
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

# Expose API port
EXPOSE 8080

# Default: run API server
CMD ["python", "api_server.py"]
