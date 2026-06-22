from jobhorizon.config import AppConfig, Secrets
from jobhorizon.models import RawJob
from jobhorizon.pipeline import run_pipeline


class _FakeAdapter:
    name = "fake"

    def __init__(self, jobs):
        self._jobs = jobs

    def search(self, criteria):
        return self._jobs


def test_pipeline_dedupes_filters_scores_and_logs_run(
    conn,
    sample_criteria,
    filter_cfg,
    scoring_cfg,
    fx_rates,
    monkeypatch,
):
    sample_criteria.id = 1
    good_job = RawJob(
        source="fake",
        title="Python SQL AWS Engineer",
        company="Acme",
        location="Noida",
        work_type_hint="hybrid",
        salary_min=2000000,
        salary_max=2500000,
        salary_currency="INR",
    )
    rejected_location_job = RawJob(
        source="fake",
        title="Java Developer",
        company="Beta",
        location="Gurgaon",
        work_type_hint="hybrid",
        salary_max=2500000,
        salary_currency="INR",
    )
    adapter = _FakeAdapter([good_job, rejected_location_job])
    monkeypatch.setattr("jobhorizon.pipeline.build_adapters", lambda cfg: [adapter])

    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )
    result = run_pipeline(conn, sample_criteria, app_config)

    assert result["n_fetched"] == 2
    assert result["n_new"] == 2
    assert result["n_gate_passed"] == 1
    assert len(result["new_gate_passed_rows"]) == 1
    assert result["new_gate_passed_rows"][0]["title"] == "Python SQL AWS Engineer"

    assert conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 2
    assert conn.execute("SELECT COUNT(*) c FROM job_score WHERE gate_passed=1").fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM review").fetchone()["c"] == 2

    run_row = conn.execute("SELECT * FROM runs").fetchone()
    assert run_row["n_fetched"] == 2
    assert run_row["n_new"] == 2
    assert run_row["n_gate_passed"] == 1
    assert run_row["sources"] == "fake"


def test_pipeline_second_run_does_not_recount_existing_as_new(
    conn,
    sample_criteria,
    filter_cfg,
    scoring_cfg,
    fx_rates,
    monkeypatch,
):
    sample_criteria.id = 1
    job = RawJob(
        source="fake",
        title="Python Engineer",
        company="Acme",
        location="Noida",
        work_type_hint="hybrid",
        salary_max=2500000,
        salary_currency="INR",
    )
    adapter = _FakeAdapter([job])
    monkeypatch.setattr("jobhorizon.pipeline.build_adapters", lambda cfg: [adapter])
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )

    first = run_pipeline(conn, sample_criteria, app_config)
    second = run_pipeline(conn, sample_criteria, app_config)

    assert first["n_new"] == 1
    assert second["n_new"] == 0
    assert second["n_gate_passed"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 1
