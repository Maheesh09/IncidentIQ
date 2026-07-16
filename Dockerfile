# Dockerfile
FROM python:3.11-alpine AS builder

WORKDIR /app

# Alpine uses apk instead of apt-get
RUN apk add --no-cache gcc musl-dev libpq-dev

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.11-alpine AS runtime

WORKDIR /app

RUN apk add --no-cache libpq-dev

COPY --from=builder /install /usr/local

COPY . .

RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]