FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

ENV PYTHONPATH=/app/src
ENV DB_HOST=host.docker.internal
ENV DB_PORT=3306
ENV DB_USER=jckchen
ENV DB_PASSWORD=123
ENV DB_NAME=stock_market
ENV CRAWLER_DELAY=0.1
ENV CRAWLER_TIMEOUT=15

EXPOSE 8000

CMD ["uvicorn", "stock_platform.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
