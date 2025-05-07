FROM python:3.13-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/roperscrossroads/meshinfo-lite"
LABEL org.opencontainers.image.description="Realtime web UI to run against a Meshtastic regional or private mesh network."

ENV MQTT_TLS=false \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.local/bin:${PATH}" \
    APP_PORT=8000

RUN groupadd --system app && \
    useradd --system --gid app --home-dir /app --create-home app

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libexpat1 libcairo2 pkg-config fonts-symbola fontconfig freetype2-demos && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    fc-cache -fv

COPY requirements.txt banner run.sh ./

RUN pip install --upgrade pip && \
    su app -c "pip install --no-cache-dir --user -r requirements.txt"

COPY --chown=app:app banner run.sh ./
COPY --chown=app:app *.py ./
COPY --chown=app:app www  ./www
COPY --chown=app:app templates ./templates
COPY --chown=app:app migrations ./migrations

RUN chmod 755 run.sh && chmod -R o-w /app

USER app

EXPOSE ${APP_PORT}

HEALTHCHECK CMD curl --fail http://localhost:${APP_PORT}/health || exit 1

CMD ["./run.sh"]
