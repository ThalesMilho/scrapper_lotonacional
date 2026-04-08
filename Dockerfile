# =============================================================================
# BASE: Matched exactly to playwright==1.47.0 in requirements.txt
# =============================================================================
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

WORKDIR /app

# Dependency layer (cached — only invalidates if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Browser binaries only — no --with-deps (base image handles system libs)
RUN playwright install chromium

# Source code (most frequently changing — copied last)
COPY . .

EXPOSE 8000

# Non-root user shipped by the Playwright image
USER pwuser

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
