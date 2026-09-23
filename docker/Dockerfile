FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MCP_HOST=0.0.0.0 MCP_PORT=8000

WORKDIR /app

RUN addgroup --system app \
    && adduser --system --ingroup app app \
    && mkdir --parents /data \
    && chown app:app /data

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir .

USER app

EXPOSE 8000

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('MCP_PORT', '8000') + '/healthz', timeout=3)"

CMD ["python", "-m", "m365_mcp"]
