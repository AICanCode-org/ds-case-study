# Unit + data tests with line coverage; fails below the gate given as the first argument (default 85).
gate <- as.numeric(commandArgs(trailingOnly = TRUE)[1])
if (is.na(gate)) gate <- 85
repo <- normalizePath("../..")
Sys.setenv(CHURNCAST_REPO = repo, CONTRACT_PATH = file.path(repo, "contract", "data-contract.yaml"))
cov <- covr::package_coverage(".", type = "tests", quiet = TRUE)
print(cov)
covr::to_cobertura(cov, "coverage.xml")
p <- covr::percent_coverage(cov)
cat(sprintf("Total coverage: %.2f%%\n", p))
if (p < gate) quit(status = 1)
