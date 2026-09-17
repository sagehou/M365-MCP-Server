FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml* ./

COPY . .

RUN pip install --no-cache-dir . || true

EXPOSE 8000

CMD ["python", "-m", "m365_mcp"]
