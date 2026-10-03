# ChurnCast pipeline, SQL track (DuckDB). Build from the repo root:
#   docker build -f tracks/sql/Dockerfile -t churncast-sql:local .
FROM scratch AS src
COPY contract /app/contract
COPY tracks/sql/sql /app/tracks/sql/sql
COPY tracks/sql/churncast_sql /app/tracks/sql/churncast_sql

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN --mount=type=bind,source=tracks/sql/requirements.txt,target=/tmp/requirements.txt \
    pip install -r /tmp/requirements.txt \
 && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin churncast \
 && mkdir -p /out && chown 10001:10001 /out
COPY --from=src /app /app
WORKDIR /app/tracks/sql
USER 10001
ENTRYPOINT ["python", "-m", "churncast_sql"]
CMD ["run", "--data", "/app/data/raw/2026-05", "--out", "/out"]
