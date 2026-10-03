skip_if_pending("test-data-retraining.R")
# M7 on the real 2026-07 export: monitoring catches the June price change, the challenger beats the champion.

mon <- function() real_result()$metrics$monitoring
rt <- function() real_result()$metrics$retraining
by_snapshot <- function(rows, snap) Filter(function(r) r$snapshot == snap, rows)[[1]]

test_that("post-deployment snapshots are split by role", {
  roles <- vapply(mon()$drift, function(d) d$split, "")
  expect_identical(roles, c("recent", "holdout", "score"))
  expect_identical(vapply(mon()$drift, function(d) d$snapshot, ""), c("2026-05", "2026-06", "2026-07"))
})

test_that("the June price change is flagged as drift", {
  june <- by_snapshot(mon()$drift, "2026-06")
  expect_identical(june$features_drift, list("price_change_pct"))
  expect_gt(june$feature_psi$price_change_pct, 1)
  expect_identical(by_snapshot(mon()$drift, "2026-05")$features_drift, list())
})

test_that("the deployed model still ranks but is miscalibrated", {
  june <- by_snapshot(mon()$performance, "2026-06")
  expect_gt(june$auc, 0.72)
  expect_gt(june$ece, 0.03)
  expect_gt(june$observed_rate - june$mean_pred, 0.05)
  expect_identical(mon()$status, "retrain")
  expect_identical(vapply(mon()$performance, function(p) p$snapshot, ""), c("2026-05", "2026-06"))
})

test_that("the challenger is refitted, recalibrated and wins on the holdout month", {
  c <- rt()$challenger
  expect_identical(unlist(c$refit_snapshots), c(sprintf("2025-%02d", 9:12), sprintf("2026-%02d", 1:4)))
  expect_identical(c$calibration_snapshot, "2026-05")
  expect_gt(c$calibration_offset, 0)
  ch <- rt()$champion_holdout
  cc <- rt()$challenger_holdout
  expect_lt(cc$brier, ch$brier)
  expect_lt(cc$ece, 0.03)
  expect_true(rt()$gate$passed)
  expect_identical(rt()$decision, "promote")
})

test_that("the promoted artefact records its lineage", {
  a <- real_result()$artefact
  expect_identical(a$model_version, "1.1.0")
  expect_identical(a$lineage$parent_model_version, "1.0.0")
  expect_identical(a$lineage$decision, "promote")
  expect_identical(a$monitoring_reference$rows, rt()$challenger$refit_rows)
  shares <- c(lapply(a$monitoring_reference$features, function(f) sum(unlist(f$shares))),
              list(sum(unlist(a$monitoring_reference$score$shares))))
  expect_true(all(abs(unlist(shares) - 1) < 1e-12))
})

test_that("the v1.0 contract rejects the new export", {
  # the incident behind the 1.1.0 contract: marketing launched an influencer channel in June 2026
  old <- file.path(CONTRACT_DIR, "history", "data-contract-1.0.0.yaml")
  code <- run_cli(c("run", "--data", EXPORT_V11, "--out", tempfile("out"), "--contract", old))
  expect_identical(as.integer(code), 3L)
  expect_match(attr(code, "stderr"), "customers.channel.accepted", fixed = TRUE)
})

test_that("the deployed model path can be overridden", {
  withr_path <- tempfile(fileext = ".json")
  file.copy(file.path(REPO, "models", "churncast-1.0.0.json"), withr_path)
  old <- Sys.getenv("DEPLOYED_MODEL_PATH")
  Sys.setenv(DEPLOYED_MODEL_PATH = withr_path)
  on.exit(Sys.setenv(DEPLOYED_MODEL_PATH = old))
  expect_identical(load_deployed(CONTRACT)$model_version, "1.0.0")
})
