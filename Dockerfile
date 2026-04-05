# Dockerfile for Q-SEED Development Environment
FROM python:3.13-slim-bookworm

# 1. System dependencies and Google Cloud SDK
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    git \
    build-essential \
    && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - \
    && apt-get update && apt-get install -y google-cloud-cli \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2. Install uv (Package Manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 3. Set working directory
WORKDIR /app

# 4. Install Python dependencies including dbt
# dbt-core and a specific adapter (e.g., dbt-bigquery if using GCS/BigQuery)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# 5. Application setup
COPY . .
RUN uv sync --frozen

# 6. Default command
CMD ["/bin/bash"]
