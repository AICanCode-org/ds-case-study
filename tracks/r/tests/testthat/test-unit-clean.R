skip_if_pending("test-unit-clean.R")

TS <- c("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M")

test_that("labels are trimmed and lower-cased", {
  expect_identical(normalise_label(c("  PUNE ", "")), c("pune", ""))
})

test_that("two timestamp formats, day first, nothing else", {
  got <- parse_with(c("2026-01-31 23:00:00", "05/02/2026 10:30", "2026-02-30 10:00:00", "2026/01/05", "",
                      "2026-01-31 23:00:00 extra"), TS)
  expect_equal(format(got[1:2], "%Y-%m-%d %H:%M"), c("2026-01-31 23:00", "2026-02-05 10:30"))
  expect_true(all(is.na(got[3:6])))
})

test_that("money arrives as text", {
  expect_identical(parse_money(c("3299", "3,299.00", "\u20b93,299", " 4499.0 ", "-300.00", "abc", "")),
                   c(3299, 3299, 3299, 4499, -300, NA, NA))
})

test_that("month_index counts months", {
  expect_identical(month_index("2026-01") - month_index("2025-11"), 2L)
})

test_that("issue counts come in the contract order", {
  got <- tiny()$issues
  expect_identical(names(got), ISSUE_ORDER)
  expect_equal(got, EXPECTED$issues[ISSUE_ORDER])
})

test_that("clean row counts", {
  expect_equal(lapply(tiny()$tables, nrow), EXPECTED$clean_rows[c("customers", "invoices", "usage", "tickets")])
})

test_that("labels are normalised and aliased", {
  c <- tiny()$tables$customers
  row <- function(id) c[c$customer_id == id, ]
  expect_identical(row("C00002")$city, "bengaluru")
  expect_identical(row("C00004")$acquisition_channel, "referral")
  expect_identical(row("C00003")$acquisition_channel, "unknown")
  expect_identical(row("C00003")$signup_date, "2025-12-10")
  expect_false("C00005" %in% c$customer_id)
})

test_that("a resolution before the ticket was created becomes unresolved", {
  t <- tiny()$tables$tickets
  expect_true(is.na(t$resolved[t$ticket_id == "T000005"]))
})

test_that("refunds are kept but never count as charges", {
  inv <- tiny()$tables$invoices
  expect_identical(inv$list_price[inv$kind == "refund"], -300)
})
