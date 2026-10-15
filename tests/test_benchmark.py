"""Proves the benchmark scoring math and that a full autostart run detects every
planted bug with no false positives (detection_rate 1.0)."""
import benchmark


# ---- pure scoring ---------------------------------------------------------

def test_score_counts_tp_fn_fp_tn():
    results = [
        {"class": "idor", "kind": "positive", "passed": True},
        {"class": "idor", "kind": "positive", "passed": False},   # missed bug
        {"class": "idor", "kind": "negative", "passed": True},    # correctly clean
        {"class": "mcp", "kind": "negative", "passed": False},    # false positive
    ]
    sc = benchmark.score(results)
    assert sc["true_positives"] == 1 and sc["false_negatives"] == 1
    assert sc["true_negatives"] == 1 and sc["false_positives"] == 1
    assert sc["detection_rate"] == 0.5
    assert sc["per_class"]["idor"] == {"passed": 2, "total": 3}


# ---- live autostart integration ------------------------------------------

def test_autostart_full_detection():
    # starts both bundled labs, runs every probe, requires a perfect score
    rc = benchmark.main(["--autostart", "--min-rate", "1.0"])
    assert rc == 0        # non-zero would mean a planted bug went undetected
