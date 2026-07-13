# Python 3.12 (matches .python-version and pyproject.toml)
FROM python:3.12-slim

ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID

LABEL maintainer="Q-SEED Team"
LABEL description="Q-SEED Quantitative Investment Research Platform"
LABEL python.version="3.12"

# Native extensions (duckdb, cryptography, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir -p /app/data /app/logs \
    && chown -R $USERNAME:$USERNAME /app

WORKDIR /app

COPY --chown=$USERNAME:$USERNAME pyproject.toml uv.lock ./

RUN uv sync --frozen --no-editable

COPY --chown=$USERNAME:$USERNAME . .

USER $USERNAME

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV DBT_PROFILES_DIR=/app

CMD ["bash"]
