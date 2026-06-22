import json

from jobhorizon import db, learner
from jobhorizon.config import AppConfig, Secrets


def _insert_label(
    conn,
    *,
    relevant,
    from_discard=False,
    title="Python Engineer",
    source="remoteok",
    work_type="remote",
    salary_band="10-20L",
    skills_matched=2,
    domain_hits=0,
    location="Noida",
    location_match=True,
):
    feature_dict = {
        "title": title,
        "skills_matched": skills_matched,
        "domain_hits": domain_hits,
        "source": source,
        "work_type": work_type,
        "salary_band": salary_band,
        "location_match": location_match,
    }
    db.insert_label(
        conn,
        {
            "relevant": relevant,
            "from_discard": from_discard,
            "title": title,
            "company": "Acme",
            "source": source,
            "work_type": work_type,
            "location": location,
            "salary_min_inr": 1200000,
            "skills_matched": skills_matched,
            "skills_matched_list": json.dumps(["Python"]),
            "domain_hits": domain_hits,
            "feature_json": json.dumps(feature_dict),
        },
    )


def _insert_job(conn, job_id, score, gate_passed=True):
    job = {
        "job_id": job_id,
        "source": "remoteok",
        "external_id": "1",
        "url": "http://x",
        "title": "Python Engineer",
        "company": "Acme",
        "location": "Noida",
        "work_type": "remote",
        "description": "",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_min_inr": 1200000,
        "salary_max_inr": 1500000,
        "poster_name": None,
        "poster_email": None,
        "posted_date": None,
        "raw_json": "{}",
    }
    db.upsert_job(conn, job)
    db.replace_job_score(
        conn,
        {
            "job_id": job_id,
            "gate_passed": gate_passed,
            "gate_reason": "passed",
            "skills_matched": 2,
            "skills_matched_list": '["Python"]',
            "score": score,
            "model_source": "deterministic",
        },
    )
    db.ensure_review_row(conn, job_id)
    conn.commit()


def test_count_labels(conn):
    assert learner.count_labels(conn) == 0
    _insert_label(conn, relevant=True)
    assert learner.count_labels(conn) == 1


def test_train_model_requires_both_classes(conn):
    _insert_label(conn, relevant=True)
    _insert_label(conn, relevant=True)
    pipeline, report = learner.train_model(conn)
    assert pipeline is None
    assert "error" in report


def test_train_model_fits_with_both_classes(conn):
    for i in range(5):
        _insert_label(conn, relevant=True, title=f"Python Engineer {i}", source="remoteok")
    for i in range(5):
        _insert_label(
            conn,
            relevant=False,
            title=f"Sales Manager {i}",
            source="naukri",
            work_type="onsite",
            skills_matched=0,
        )

    pipeline, report = learner.train_model(conn)

    assert pipeline is not None
    assert report["n_labels"] == 10
    assert len(report["top_features"]) > 0


def test_score_with_learner_returns_clamped_probabilities(conn, scoring_cfg, filter_cfg):
    for i in range(5):
        _insert_label(conn, relevant=True, title=f"Python Engineer {i}")
    for i in range(5):
        _insert_label(
            conn,
            relevant=False,
            title=f"Sales Manager {i}",
            skills_matched=0,
            source="naukri",
            work_type="onsite",
        )
    pipeline, _ = learner.train_model(conn)

    job_rows = [
        {
            "title": "Python Engineer",
            "description": "",
            "skills_matched": 2,
            "source": "remoteok",
            "work_type": "remote",
            "salary_min_inr": 1200000,
            "location": "Noida",
        }
    ]
    scores = learner.score_with_learner(pipeline, job_rows, scoring_cfg, filter_cfg.location_aliases)

    assert len(scores) == 1
    assert 0.0 <= scores[0] <= 1.0


def test_maybe_retrain_and_rescore_below_threshold(conn, sample_criteria, scoring_cfg, filter_cfg, fx_rates):
    scoring_cfg.learner_min_labels = 5
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )
    _insert_label(conn, relevant=True)

    assert learner.maybe_retrain_and_rescore(conn, sample_criteria, app_config) is None


def test_maybe_retrain_and_rescore_updates_job_score(
    conn, sample_criteria, scoring_cfg, filter_cfg, fx_rates
):
    scoring_cfg.learner_min_labels = 4
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )
    for i in range(2):
        _insert_label(conn, relevant=True, title=f"Python Engineer {i}")
    for i in range(2):
        _insert_label(
            conn,
            relevant=False,
            title=f"Sales Manager {i}",
            skills_matched=0,
            source="naukri",
            work_type="onsite",
        )
    _insert_job(conn, "job1", score=0.5)

    report = learner.maybe_retrain_and_rescore(conn, sample_criteria, app_config)

    assert report is not None
    assert "top_features" in report
    row = conn.execute("SELECT model_source, score FROM job_score WHERE job_id='job1'").fetchone()
    assert row["model_source"] == "learner"
    assert 0.0 <= row["score"] <= 1.0


def test_compute_metrics(conn):
    assert learner.compute_metrics(conn) == {}
    _insert_label(conn, relevant=True, from_discard=False)
    _insert_label(conn, relevant=False, from_discard=False)
    _insert_label(conn, relevant=True, from_discard=True)

    metrics = learner.compute_metrics(conn)

    assert metrics["n_labels"] == 3
    assert metrics["precision_at_k"] == 0.5
    assert metrics["discard_rescue_rate"] == 1.0


def test_rescue_hint_triggers_at_two_shared_source(conn):
    assert learner.rescue_hint(conn) is None
    _insert_label(conn, relevant=True, from_discard=True, source="arbeitnow")
    assert learner.rescue_hint(conn) is None

    _insert_label(conn, relevant=True, from_discard=True, source="arbeitnow")
    hint = learner.rescue_hint(conn)

    assert hint is not None
    assert "arbeitnow" in hint
