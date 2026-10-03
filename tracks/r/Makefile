# R track (tidymodels + R Markdown). Same targets in every track: install, lint, test, coverage, run, report, gate.
# The toolchain is pinned in tracks/r/Dockerfile (R 4.6.1 + a dated CRAN snapshot); CI runs these targets in it:
#   docker build -f tracks/r/Dockerfile --target dev -t churncast-r-dev:local .     (from the repo root)
#   docker run --rm -v "$PWD":/repo -w /repo/tracks/r churncast-r-dev:local make test
R ?= Rscript
DATA ?= ../../data/raw/2026-05
OUT ?= out

.PHONY: install lint test coverage run report gate clean
install:         ## without Docker: the packages of DESCRIPTION from the same CRAN snapshot
	$(R) -e 'install.packages(c("parsnip", "workflows", "rsample", "yardstick", "dplyr", "readr", "jsonlite", "yaml", "tibble", "pkgload", "lintr", "testthat", "covr", "rmarkdown", "knitr", "ggplot2"), repos = "https://p3m.dev/cran/2026-09-15")'

lint:
	$(R) -e 'l <- lintr::lint_package("."); print(l); if (length(l) > 0) quit(status = 1)'

test:            ## unit tests (fast, tiny fixtures)
	$(R) -e 'testthat::test_local(".", filter = "^unit-", reporter = "summary", stop_on_failure = TRUE)'

coverage:        ## unit + data/model tests on the real export, 85 % line coverage gate
	$(R) tools/coverage.R 85

run:             ## features.csv, metrics.json, model.json, experiments.jsonl for one export
	$(R) run.R run --data $(DATA) --out $(OUT)

report:          ## knit report/churn-model.Rmd to out/churn-model.html (fails on any error)
	$(R) -e 'd <- normalizePath("$(DATA)"); o <- normalizePath("$(OUT)", mustWork = FALSE); rmarkdown::render("report/churn-model.Rmd", output_dir = o, params = list(data = d), quiet = TRUE)'

gate:            ## the evaluation gate of out/metrics.json (exit 1 if any check fails)
	python3 ../../scripts/eval_gate.py $(OUT)/metrics.json

clean:
	rm -rf $(OUT) coverage.xml report/*_files report/*.html
