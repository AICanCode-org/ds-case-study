# ChurnCast, R track. One pinned toolchain for laptops and CI: R 4.6.1 (rocker) + a dated Posit Package Manager
# snapshot of CRAN, so tidymodels, lintr and testthat are the same versions everywhere.
#   docker build -f tracks/r/Dockerfile --target dev -t churncast-r-dev:local .     (lint, tests, report)
#   docker build -f tracks/r/Dockerfile -t churncast-r:local .                     (the pipeline, non-root)
FROM rocker/r-ver:4.6.1 AS base
ENV CRAN=https://p3m.dev/cran/__linux__/noble/2026-09-15 LANG=C.UTF-8 HOME=/tmp
RUN install2.r --error --skipinstalled -n 4 -r "$CRAN" dplyr tidyr readr jsonlite yaml tibble rlang recipes parsnip workflows rsample yardstick pkgload \
 && rm -rf /tmp/downloaded_packages /tmp/Rtmp*

# dev: what `make lint test coverage report` needs (CI runs the R job in this image with the repo mounted)
FROM base AS dev
# apt over HTTPS: some networks and proxies block plain-HTTP package mirrors
RUN sed -i 's|http://|https://|g' /etc/apt/sources.list.d/ubuntu.sources \
 && apt-get update && apt-get install -y --no-install-recommends pandoc make && rm -rf /var/lib/apt/lists/* \
 && install2.r --error --skipinstalled -n 4 -r "$CRAN" lintr testthat covr rmarkdown knitr ggplot2 \
 && rm -rf /tmp/downloaded_packages /tmp/Rtmp*

# runtime: the pipeline only, as a non-root user (two layers on top of base: vfs/overlay copies stay small)
FROM scratch AS src
COPY contract /app/contract
COPY models /app/models
COPY tracks/r/DESCRIPTION tracks/r/NAMESPACE tracks/r/LICENSE tracks/r/run.R /app/tracks/r/
COPY tracks/r/R /app/tracks/r/R

FROM base AS runtime
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin churncast && mkdir -p /out && chown 10001:10001 /out
COPY --from=src /app /app
WORKDIR /app/tracks/r
USER 10001
ENTRYPOINT ["Rscript", "run.R"]
CMD ["run", "--data", "/app/data/raw/2026-07", "--out", "/out"]
