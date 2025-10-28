FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY . /app

# Install Python requirements if present
RUN if [ -f requirements.txt ]; then python -m pip install --no-cache-dir -r requirements.txt; fi

# Ensure entrypoint is executable
RUN chmod +x /app/entrypoint.sh || true

# Create a directory for downloaded manga (can be mounted)
RUN mkdir -p /data/manga /var/log/blue-scraper

VOLUME ["/data/manga"]

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["--help"]
