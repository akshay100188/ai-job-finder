from jobhorizon.models import RawJob
from jobhorizon.normalize import normalize_job

FX = {"INR": 1.0, "USD": 86.0}


def test_work_type_hint_wins_over_text():
    raw = RawJob(
        source="x", title="Backend Engineer", description="hybrid role mentioned", work_type_hint="remote"
    )
    row = normalize_job(raw, FX)
    assert row["work_type"] == "remote"


def test_work_type_keyword_fallback_single_match():
    raw = RawJob(source="x", title="Remote Backend Engineer", description="Work from anywhere")
    row = normalize_job(raw, FX)
    assert row["work_type"] == "remote"


def test_work_type_unknown_when_ambiguous_or_absent():
    raw = RawJob(source="x", title="Backend Engineer", description="Great team, great pay")
    row = normalize_job(raw, FX)
    assert row["work_type"] == "unknown"


def test_work_type_unknown_when_multiple_keywords_present():
    raw = RawJob(source="x", title="Hybrid/Remote Backend Engineer", description="")
    row = normalize_job(raw, FX)
    assert row["work_type"] == "unknown"


def test_salary_converted_to_inr():
    raw = RawJob(source="x", title="t", salary_min=1000, salary_max=2000, salary_currency="USD")
    row = normalize_job(raw, FX)
    assert row["salary_min_inr"] == 86000
    assert row["salary_max_inr"] == 172000


def test_salary_missing_currency_left_null_recall_bias():
    raw = RawJob(source="x", title="t", salary_min=1000, salary_max=2000, salary_currency="XYZ")
    row = normalize_job(raw, FX)
    assert row["salary_min_inr"] is None
    assert row["salary_max_inr"] is None


def test_salary_absent_left_null():
    raw = RawJob(source="x", title="t")
    row = normalize_job(raw, FX)
    assert row["salary_min_inr"] is None
    assert row["salary_max_inr"] is None
