# ChurnCast prediction API (the v1.0 release). Build from the repo root:
#   docker build -f serving/Dockerfile -t churncast-api:local .
# Serves models/churncast-1.0.0.json by default; MODEL_PATH picks another artefact (any track's model.json).
FROM scratch AS src
COPY contract/data-contract.yaml contract/model.schema.json /app/contract/
COPY models /app/models
COPY serving/churncast_api /app/serving/churncast_api
COPY serving/static /app/serving/static

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp AI_PROVIDER=offline MODEL_PATH=/app/models/churncast-1.0.0.json
RUN --mount=type=bind,source=serving/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin churncast
COPY --from=src /app /app
WORKDIR /app/serving
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=5s --timeout=3s --start-period=10s --retries=12 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
ENTRYPOINT ["python", "-m", "churncast_api", "--host", "0.0.0.0", "--port", "8000"]
