# M1 · Cleaning rules of contract/feature-spec.md §2, in the written order. Every rule that drops or changes rows
# counts them in `issues`, so rows read = rows kept + rows dropped can be checked (Phase 4 invariants).

ISSUE_ORDER <- c(
  "customers_invalid_signup_date", "customers_exact_duplicates", "customers_channel_missing",
  "customers_age_band_missing", "invoices_exact_duplicates", "invoices_orphans", "usage_exact_duplicates",
  "usage_negative_counts", "usage_orphans", "tickets_invalid_created_at", "tickets_resolved_before_created",
  "tickets_orphans"
)
COUNTS <- c("meals_ordered", "meals_skipped", "late_deliveries", "ratings_count", "ratings_sum")

# strptime() ignores trailing text and accepts one-digit fields, so each format also has an exact pattern
FORMAT_PATTERNS <- c(
  "%Y-%m-%d %H:%M:%S" = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$",
  "%d/%m/%Y %H:%M" = "^\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2}$",
  "%Y-%m-%d" = "^\\d{4}-\\d{2}-\\d{2}$",
  "%d/%m/%Y" = "^\\d{2}/\\d{2}/\\d{4}$"
)

normalise_label <- function(x) tolower(trimws(x))

#' The first format that parses the whole value; NA when none does. Times are UTC (no daylight saving).
parse_with <- function(values, formats) {
  values <- trimws(values)
  out <- as.POSIXct(rep(NA_real_), origin = "1970-01-01", tz = "UTC")
  for (fmt in formats) {
    pattern <- FORMAT_PATTERNS[[fmt]]
    todo <- is.na(out) & grepl(pattern, values, perl = TRUE)
    if (any(todo)) out[todo] <- as.POSIXct(strptime(values[todo], fmt, tz = "UTC"))
  }
  out
}

#' "₹3,299", "3,299.00", " 3299.0 ", "-150.00" -> rupees; anything else -> NA.
parse_money <- function(x) {
  text <- trimws(gsub(",", "", gsub("\u20b9", "", x, fixed = TRUE), fixed = TRUE))
  ok <- grepl("^[+-]?(\\d+\\.?\\d*|\\.\\d+)$", text, perl = TRUE)
  out <- rep(NA_real_, length(x))
  out[ok] <- round(as.numeric(text[ok]), 2)
  out
}

month_index <- function(x) {
  parts <- strsplit(trimws(x), "-", fixed = TRUE)
  vapply(parts, function(p) as.integer(p[1]) * 12L + as.integer(p[2]) - 1L, integer(1))
}

clean_customers <- function(raw, contract, issues) {
  rules <- contract$cleaning
  signup <- parse_with(raw$signup_date, unlist(rules$date_formats))
  bad <- is.na(signup)
  issues$customers_invalid_signup_date <- sum(bad)
  df <- raw[!bad, , drop = FALSE]
  signup <- signup[!bad]
  dup <- duplicated(df[unlist(contract$files$customers$columns)])
  issues$customers_exact_duplicates <- sum(dup)
  df <- df[!dup, , drop = FALSE]
  signup <- signup[!dup]
  city <- normalise_label(df$city)
  aliases <- unlist(rules$city_aliases)
  city <- ifelse(city %in% names(aliases), aliases[city], city)
  missing <- rules$missing_label
  channel <- normalise_label(df$acquisition_channel)
  issues$customers_channel_missing <- sum(channel == "")
  age <- normalise_label(df$age_band)
  issues$customers_age_band_missing <- sum(age == "")
  tiers <- unlist(rules$city_tier)
  lt <- as.POSIXlt(signup)
  out <- data.frame(
    customer_id = trimws(df$customer_id),
    signup_date = format(signup, "%Y-%m-%d"),
    signup_month = (lt$year + 1900L) * 12L + lt$mon,
    city = unname(city),
    city_tier = unname(ifelse(city %in% names(tiers), tiers[city], missing)),
    acquisition_channel = ifelse(channel == "", missing, channel),
    age_band = ifelse(age == "", missing, age),
    cancellation_reason = df$cancellation_reason,
    stringsAsFactors = FALSE
  )
  list(table = out, issues = issues)
}

clean_invoices <- function(raw, customers, issues) {
  dup <- duplicated(raw)
  issues$invoices_exact_duplicates <- sum(dup)
  df <- raw[!dup, , drop = FALSE]
  known <- df$customer_id %in% customers$customer_id
  issues$invoices_orphans <- sum(!known)
  df <- df[known, , drop = FALSE]
  out <- data.frame(
    invoice_id = df$invoice_id,
    customer_id = df$customer_id,
    billing_month = df$billing_month,
    month = month_index(df$billing_month),
    kind = normalise_label(df$kind),
    plan = normalise_label(df$plan),
    list_price = parse_money(df$list_price),
    discount = parse_money(df$discount),
    status = normalise_label(df$status),
    stringsAsFactors = FALSE
  )
  list(table = out, issues = issues)
}

clean_usage <- function(raw, customers, issues) {
  dup <- duplicated(raw)
  issues$usage_exact_duplicates <- sum(dup)
  df <- raw[!dup, , drop = FALSE]
  for (col in COUNTS) df[[col]] <- as.integer(df[[col]])
  negative <- Reduce(`|`, lapply(COUNTS, function(col) df[[col]] < 0))
  issues$usage_negative_counts <- sum(negative)
  df <- df[!negative, , drop = FALSE]
  known <- df$customer_id %in% customers$customer_id
  issues$usage_orphans <- sum(!known)
  df <- df[known, , drop = FALSE]
  df$month <- month_index(df$month)
  list(table = df[c("customer_id", "month", COUNTS)], issues = issues)
}

clean_tickets <- function(raw, customers, contract, issues) {
  formats <- unlist(contract$cleaning$timestamp_formats)
  created <- parse_with(raw$created_at, formats)
  bad <- is.na(created)
  issues$tickets_invalid_created_at <- sum(bad)
  df <- raw[!bad, , drop = FALSE]
  created <- created[!bad]
  resolved <- parse_with(df$resolved_at, formats)  # blank -> NA
  backwards <- !is.na(resolved) & resolved < created
  issues$tickets_resolved_before_created <- sum(backwards)
  resolved[backwards] <- NA
  known <- df$customer_id %in% customers$customer_id
  issues$tickets_orphans <- sum(!known)
  out <- data.frame(
    ticket_id = df$ticket_id,
    customer_id = df$customer_id,
    created = created,
    category = normalise_label(df$category),
    resolved = resolved,
    stringsAsFactors = FALSE
  )
  list(table = out[known, , drop = FALSE], issues = issues)
}

clean_tables <- function(raw, contract) {
  issues <- list()
  customers <- clean_customers(raw$customers, contract, issues)
  invoices <- clean_invoices(raw$invoices, customers$table, customers$issues)
  usage <- clean_usage(raw$usage, customers$table, invoices$issues)
  tickets <- clean_tickets(raw$tickets, customers$table, contract, usage$issues)
  tables <- list(customers = customers$table, invoices = invoices$table, usage = usage$table,
                 tickets = tickets$table)
  tables <- lapply(tables, function(t) {
    rownames(t) <- NULL
    t
  })
  list(tables = tables, issues = tickets$issues[ISSUE_ORDER])
}
