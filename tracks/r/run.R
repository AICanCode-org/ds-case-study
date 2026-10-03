#!/usr/bin/env Rscript
# ChurnCast, R track. Rscript run.R run --data ../../data/raw/2026-05 --out out
# Loads the package source with pkgload (no install needed), then runs main().
suppressPackageStartupMessages(pkgload::load_all(".", quiet = TRUE, export_all = FALSE))
quit(status = main(), save = "no")
