"""Properties that must hold for ANY export, not just this one."""

from churncast.contract import feature_names


def test_rows_read_equal_rows_kept_plus_rows_dropped(result):
    dq = result["metrics"]["data_quality"]
    raw, clean, issues = dq["raw_rows"], dq["clean_rows"], dq["issues"]
    dropped = {
        "customers": issues["customers_invalid_signup_date"] + issues["customers_exact_duplicates"],
        "invoices": issues["invoices_exact_duplicates"] + issues["invoices_orphans"],
        "usage": issues["usage_exact_duplicates"] + issues["usage_negative_counts"] + issues["usage_orphans"],
        "tickets": issues["tickets_invalid_created_at"] + issues["tickets_orphans"],
    }
    for table in raw:
        assert raw[table] == clean[table] + dropped[table], table


def test_every_feature_is_inside_its_contract_range(result, contract):
    f = result["features"]
    for spec in contract["features"]:
        col = f[spec["name"]]
        assert col.notna().all(), spec["name"]
        assert col.between(spec["min"], spec["max"]).all(), spec["name"]
        if spec["type"] == "binary":
            assert set(col.unique()) <= {0.0, 1.0}


def test_one_row_per_customer_and_snapshot(result):
    f = result["features"]
    assert not f.duplicated(["customer_id", "snapshot"]).any()


def test_no_customer_sits_in_two_folds_and_test_comes_after_train(result):
    m = result["metrics"]
    assert m["split"]["customers_in_two_folds"] == 0
    assert max(m["split"]["train_snapshots"]) < min(m["split"]["test_snapshots"])
    assert sum(f["rows"] for f in m["split"]["folds"]) == m["split"]["train_rows"]


def test_labels_exist_for_every_train_and_test_row(result):
    f = result["features"]
    assert f[f["split"].isin(["train", "test"])]["churned"].notna().all()


def test_contributions_explain_the_prediction_exactly(result, contract):
    from churncast.artefact import contributions, score

    a = result["artefact"]
    row = result["features"].iloc[0][feature_names(contract)].to_dict()
    eta = a["intercept"] + sum(b * a["feature_means"][f] for f, b in a["coefficients"].items())
    p = score(a, row)
    total = sum(r["contribution"] for r in contributions(a, row))
    import math

    assert math.isclose(eta + total, math.log(p / (1 - p)), abs_tol=1e-9)
