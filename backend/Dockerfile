FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_MEDIA_ROOT=/app/models

WORKDIR /app

COPY requirements.txt .
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN python -m pip install --no-cache-dir -r requirements.txt --extra-index-url "${TORCH_INDEX_URL}"

RUN useradd --create-home --uid 10001 appuser

COPY manage.py .
COPY sample_data/ ./sample_data/
COPY config/ ./config/
COPY health/ ./health/
COPY devices/ ./devices/
COPY accounts/ ./accounts/
COPY algorithms/ ./algorithms/
COPY dat_imports/ ./dat_imports/

RUN mkdir -p /app/models && chown appuser:appuser /app/models

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
