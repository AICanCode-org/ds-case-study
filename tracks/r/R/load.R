# M1 · Load the raw export as text: no type guessing, empty cells stay empty strings.

load_raw <- function(data_dir, contract) {
  tables <- list()
  for (name in names(contract$files)) {
    spec <- contract$files[[name]]
    path <- file.path(data_dir, spec$file)
    if (!file.exists(path)) contract_error(paste0("missing file: ", spec$file))
    df <- readr::read_csv(path, col_types = readr::cols(.default = readr::col_character()), na = character(),
                          trim_ws = FALSE, progress = FALSE, show_col_types = FALSE)
    missing <- setdiff(unlist(spec$columns), names(df))
    if (length(missing) > 0) {
      contract_error(paste0(spec$file, ": missing column(s) ", paste(missing, collapse = ", ")))
    }
    tables[[name]] <- as.data.frame(df[unlist(spec$columns)], stringsAsFactors = FALSE)
  }
  tables
}

load_export <- function(data_dir) {
  path <- file.path(data_dir, "export.json")
  if (!file.exists(path)) contract_error("missing file: export.json")
  jsonlite::read_json(path)
}
