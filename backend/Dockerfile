FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy source code
COPY . /app

# Expose port
EXPOSE 5000

# Run Flask application with Gunicorn
CMD ["python", "-m", "flask", "--app", "backend/app.py", "run", "--host=0.0.0.0", "--port=5000"]
