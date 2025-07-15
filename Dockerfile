FROM python:3.12.11-bookworm AS builder

# Set environment
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_DEFAULT_TIMEOUT=100

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
COPY run-public_hub_services.py ./run-public_hub_services.py
COPY gunicorn.conf.py ./gunicorn.conf.py

# Creating directories
RUN mkdir -p /app/logs
ENV LOGGER_DIR=/app/logs

# Adding non-root user
RUN adduser public-services-user
RUN chown -R public-services-user:public-services-user /app
RUN chown -R public-services-user:public-services-user /var/log
USER public-services-user

# Remove cache to reduce container size
RUN rm -rf ~/.cache/uv

# RUN
ENV SERVER_DEBUG=0
CMD ["gunicorn", "--config", "gunicorn.conf.py", "run-public_hub_services:app"]
