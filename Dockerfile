FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY config.example.yaml ./

# Install dependencies
RUN pip install --no-cache-dir -e .

# Create volume for token storage
VOLUME ["/app/data"]

# Add healthcheck
HEALTHCHECK --interval=5m --timeout=10s --start-period=10s --retries=3 \
  CMD python -m anilist_mal_sync.healthcheck || exit 1

# Run sync with config validation and auto-retry
CMD ["anilist-mal-sync", "run", "--wait-for-config"]
