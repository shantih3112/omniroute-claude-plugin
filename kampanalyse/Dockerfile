FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Europe/Oslo
WORKDIR /app
RUN useradd --create-home --uid 1000 bot && mkdir -p /data && chown bot /data

COPY pyproject.toml ./
COPY kampanalyse ./kampanalyse
RUN pip install --no-cache-dir .

USER bot
ENV DB_PATH=/data/kampanalyse.db
VOLUME ["/data"]
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
  CMD python -m kampanalyse healthcheck || exit 1
CMD ["python", "-m", "kampanalyse", "run"]
