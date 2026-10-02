# Build context is the REPO ROOT:  docker build -f hamdam/Dockerfile -t hamdam .
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY hamdam/requirements.txt .
RUN pip install -r requirements.txt
COPY hamdam/ ./hamdam/
RUN useradd -m -u 10001 appuser && chown -R appuser /app
USER appuser
EXPOSE 8090
CMD ["python", "-m", "hamdam.main"]
