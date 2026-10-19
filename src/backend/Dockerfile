FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Compose passes "[dev]" for local tooling; deployments install runtime deps only.
ARG PIP_EXTRAS=""

COPY pyproject.toml .
COPY app ./app

RUN pip install --no-cache-dir ".${PIP_EXTRAS}"

EXPOSE 8000

# Hosting platforms such as Render inject PORT; local runs fall back to 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
