# Dockerfile
# Base image: python:3.11-alpine, pinned by digest for reproducible builds.
FROM python@sha256:0d55920083f1ce1e38ac292e2772f924b4f8bb4188d336c79bf66963039e6146 AS builder

WORKDIR /app

# requirements.lock pins every transitive dependency with hashes.
# Regenerate it with the command at the top of the file after changing requirements.txt.
COPY requirements.lock .
RUN pip install --no-cache-dir --prefix=/install \
    --require-hashes --only-binary :all: \
    -r requirements.lock


FROM python@sha256:0d55920083f1ce1e38ac292e2772f924b4f8bb4188d336c79bf66963039e6146 AS runtime

WORKDIR /app

RUN apk upgrade --no-cache && apk add --no-cache libpq-dev

COPY --from=builder /install /usr/local

# Copy only what the application needs at runtime.
COPY alembic.ini config.py database.py main.py ./
COPY agents/ ./agents/
COPY alembic/ ./alembic/
COPY middleware/ ./middleware/
COPY models/ ./models/
COPY observability/ ./observability/
COPY pipeline/ ./pipeline/
COPY routers/ ./routers/
COPY tools/ ./tools/
COPY utils/ ./utils/

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
