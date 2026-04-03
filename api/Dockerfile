FROM python:3.12-slim

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Create non-root user before copying application files
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 appuser

COPY --chown=appuser:appgroup requirements.txt /srv/api/
RUN pip install --no-cache-dir -r /srv/api/requirements.txt

COPY --chown=appuser:appgroup . /srv/api/
RUN chmod +x /srv/api/entrypoint.sh

USER appuser

EXPOSE 8081

CMD ["/srv/api/entrypoint.sh"]
