# Base image with Python 3.14-slim (compatible with uv)
FROM python:3.14-slim

# Define build arguments and environment variables
ARG USERNAME=appuser
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Set labels for better container management
LABEL maintainer="Q-SEED Team"
LABEL description="Q-SEED Quantitative Investment Research Platform"
LABEL python.version="3.14"

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Create non-root user and setup working directory
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && mkdir -p /app/kor_ticker \
    && chown -R $USERNAME:$USERNAME /app

# Set working directory
WORKDIR /app

# Copy dependency files (leverage Docker layer caching)
COPY --chown=$USERNAME:$USERNAME pyproject.toml uv.lock ./

# Install dependencies (system-wide without virtual environment editing)
RUN uv sync --frozen --no-dev --no-editable

# Copy project code
COPY --chown=$USERNAME:$USERNAME . .

# Switch to non-root user
USER $USERNAME

# Set Python execution path (use virtual environment created by uv)
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Set default command
CMD ["python", "research/main.py"]
