FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 syncuser && chown -R syncuser:syncuser /app
USER syncuser

# Create volume for token storage
VOLUME ["/app/data"]

ENTRYPOINT ["anilist-mal-sync"]
CMD ["--help"]
