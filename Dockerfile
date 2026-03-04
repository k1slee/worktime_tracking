FROM python:3.13-slim

# System settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Moscow

WORKDIR /app

# Install system deps (for building some wheels if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install project deps
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r /app/requirements.txt

# Copy project
COPY . /app

# Create non-root user
RUN useradd -ms /bin/bash django && chown -R django:django /app
USER django

# Expose Django dev port
EXPOSE 8000

# Default ENV for Django
ENV DJANGO_SETTINGS_MODULE=config.settings \
    DJANGO_ALLOWED_HOSTS=* \
    DJANGO_DEBUG=True

# Run migrations and start Django dev server
# For production, replace with a proper WSGI server (e.g., gunicorn/uvicorn)
CMD ["bash", "-lc", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && python manage.py runserver 0.0.0.0:8000"]

