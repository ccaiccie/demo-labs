FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INCIDENTBOT_SYSLOG_HOST=0.0.0.0 \
    INCIDENTBOT_SYSLOG_PORT=5515 \
    INCIDENTBOT_HTTP_HOST=0.0.0.0 \
    INCIDENTBOT_HTTP_PORT=8097 \
    INCIDENTBOT_DB_PATH=/data/incidentbot.db

WORKDIR /app

COPY incidentbot/ /app/incidentbot/

RUN groupadd --system incidentbot \
    && useradd --system --gid incidentbot --home-dir /app --shell /usr/sbin/nologin incidentbot \
    && mkdir -p /data \
    && chown -R incidentbot:incidentbot /app /data

USER incidentbot

EXPOSE 5515/udp 8097/tcp

CMD ["python", "-m", "incidentbot.server"]
