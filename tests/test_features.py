import json

import pytest

from jobhorizon import criteria as criteria_mod
from jobhorizon import db, features
from jobhorizon.config import AppConfig, Secrets

DOMAIN_KEYWORDS = ["fixed income", "capital markets"]


def _insert_job_and_score(conn, **overrides):
    job = {
        "job_id": "abc123",
        "source": "remoteok",
        "external_id": "1",
        "url": "http://x",
        "title": "Python Backend Engineer",
        "company": "Acme",
        "location": "Noida",
        "work_type": "hybrid",
        "description": "fixed income capital markets desk",
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
    job.update(overrides)
    db.upsert_job(conn, job)
    db.replace_job_score(
        conn,
        {
            "job_id": job["job_id"],
            "gate_passed": True,
            "gate_reason": "passed",
            "skills_matched": 2,
            "skills_matched_list": '["Python", "SQL"]',
            "score": 0.66,
            "model_source": "deterministic",
        },
    )
    conn.commit()
    return job["job_id"]


def test_extract_feature_dict_salary_band_domain_hits_and_location_match(filter_cfg):
    job_row = {
        "title": "Python Backend Engineer",
        "description": "fixed income capital markets desk",
        "skills_matched": 2,
        "source": "remoteok",
        "work_type": "hybrid",
        "salary_min_inr": 1200000,
        "location": "Noida, India",
    }
    feats = features.extract_feature_dict(job_row, DOMAIN_KEYWORDS, filter_cfg.location_aliases)

    assert feats["salary_band"] == "10-20L"
    assert feats["domain_hits"] == 2
    assert feats["location_match"] is True
    assert feats["skills_matched"] == 2
    assert feats["source"] == "remoteok"
    assert feats["work_type"] == "hybrid"


def test_extract_feature_dict_unknown_salary_band_when_missing(filter_cfg):
    job_row = {"title": "x", "description": "", "skills_matched": 0, "source": "x", "work_type": "unknown"}
    feats = features.extract_feature_dict(job_row, DOMAIN_KEYWORDS, filter_cfg.location_aliases)
    assert feats["salary_band"] == "unknown"
    assert feats["location_match"] is False


def test_extract_feature_dict_location_no_match(filter_cfg):
    job_row = {
        "title": "x",
        "description": "",
        "skills_matched": 0,
        "source": "x",
        "work_type": "unknown",
        "location": "Gurgaon",
    }
    feats = features.extract_feature_dict(job_row, DOMAIN_KEYWORDS, filter_cfg.location_aliases)
    assert feats["location_match"] is False


def test_record_label_writes_row(conn, sample_criteria, scoring_cfg, filter_cfg, fx_rates):
    criteria_mod.save_criteria(conn, sample_criteria)
    job_id = _insert_job_and_score(conn)
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )

    features.record_label(conn, job_id, relevant=True, from_discard=False, app_config=app_config)

    row = conn.execute("SELECT * FROM labels").fetchone()
    assert row["relevant"] == 1
    assert row["from_discard"] == 0
    assert row["title"] == "Python Backend Engineer"
    assert row["source"] == "remoteok"
    assert row["domain_hits"] == 2
    feature_dict = json.loads(row["feature_json"])
    assert feature_dict["source"] == "remoteok"
    assert feature_dict["salary_band"] == "10-20L"


def test_record_label_no_active_criteria_defaults_to_no_domain_keywords(
    conn, scoring_cfg, filter_cfg, fx_rates
):
    job_id = _insert_job_and_score(conn)
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )

    features.record_label(conn, job_id, relevant=True, from_discard=False, app_config=app_config)

    row = conn.execute("SELECT * FROM labels").fetchone()
    assert row["domain_hits"] == 0


def test_record_label_unknown_job_raises(conn, scoring_cfg, filter_cfg, fx_rates):
    app_config = AppConfig(
        sources={}, filter=filter_cfg, scoring=scoring_cfg, fx_rates_to_inr=fx_rates, secrets=Secrets()
    )
    with pytest.raises(ValueError):
        features.record_label(conn, "nonexistent", True, False, app_config)
