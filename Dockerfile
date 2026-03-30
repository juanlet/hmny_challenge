# --- Builder stage ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install dependencies into /install prefix
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

# Copy BAML source and generate client
COPY baml_src/ baml_src/
RUN pip install --no-cache-dir baml-py \
    && python -m baml_cli generate

# --- Runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ app/
COPY --from=builder /build/baml_client/ baml_client/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
