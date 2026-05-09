FROM python:3.12-slim

# System deps needed by scipy, sentence-transformers, asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

# Copy source
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Non-root user
RUN useradd -m -u 1000 wigs && chown -R wigs:wigs /app
USER wigs

EXPOSE 8000

CMD ["uvicorn", "wigs.app:app", "--host", "0.0.0.0", "--port", "8000"]
