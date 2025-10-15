FROM python:3.12.11-bookworm AS builder

# Set environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DEFAULT_TIMEOUT=100 \
    SERVER_DEBUG=0 \
    HOST=0.0.0.0 \
    PORT=12999

# Configure Git to use HTTPS instead of SSH
RUN git config --global url."https://".insteadOf git://
RUN git config --global url."https://github.com/".insteadOf git@github.com:

WORKDIR /app

# Install uv
RUN pip install uv

# Copy only requirements first to leverage Docker caching
COPY pyproject.toml ./
RUN touch README.md

# Install dependencies
RUN uv pip install --system -e .

# Copying and installing the application code
COPY public_hub_services ./public_hub_services

# Creating directories
RUN mkdir -p /app/logs /app/data
ENV LOGGER_DIR=/app/logs

# Adding non-root user
RUN adduser --disabled-password --gecos '' public-services-user
RUN chown -R public-services-user:public-services-user /app
USER public-services-user

# Remove cache to reduce container size
RUN rm -rf ~/.cache/uv

EXPOSE $PORT

CMD ["sh", "-c", "uvicorn public_hub_services.main:app --host $HOST --port $PORT"]