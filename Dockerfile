FROM python:3.11-slim

# Install himalaya CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates cron \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://github.com/pimalaya/himalaya/releases/latest/download/himalaya-x86_64-linux.tar.gz \
    | tar xz -C /usr/local/bin/

# Install poetry
RUN pip install --no-cache-dir poetry

WORKDIR /app

# Install dependencies (cached layer)
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Copy package and default config
COPY openclaw_mail/ openclaw_mail/
COPY config/filters/_default.yaml config/filters/_default.yaml

# Install package
RUN poetry install --no-interaction --no-ansi

# Create runtime directories
RUN mkdir -p /app/logs /app/reports /app/config/filters /app/config/folder_mappings

# Default entrypoint
ENTRYPOINT ["python", "-m", "openclaw_mail.cli"]
CMD ["tidy"]
