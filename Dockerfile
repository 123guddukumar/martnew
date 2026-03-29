FROM python:3.12-slim

# System deps for psycopg2 + Pillow
RUN apt-get update && apt-get install -y \
    libpq-dev gcc libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000
