import sqlite3

import pytest

from jobhorizon import db
from jobhorizon.config import FilterConfig, LocationAliases, ScoringConfig
from jobhorizon.criteria import Criteria


@pytest.fixture
def conn(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    schema_path = tmp_path / "schema.sql"
    from jobhorizon.paths import SCHEMA_PATH

    schema_path.write_text(SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr("jobhorizon.db.DB_PATH", db_path)
    monkeypatch.setattr("jobhorizon.db.SCHEMA_PATH", schema_path)

    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def sample_criteria():
    return Criteria(
        titles=["Backend Engineer"],
        skills=["Python", "SQL", "AWS"],
        location="Noida",
        working_mode="hybrid",
        pay_min=1500000,
        pay_currency="INR",
        score_threshold=0.0,
    )


@pytest.fixture
def filter_cfg():
    return FilterConfig(
        recall_bias=True,
        location_aliases=LocationAliases(
            accept=["noida", "greater noida"],
            reject=["gurgaon", "gurugram"],
        ),
        recency_days=30,
    )


@pytest.fixture
def scoring_cfg():
    return ScoringConfig(
        skill_weights={},
        domain_keywords=["fixed income", "capital markets"],
        domain_boost=0.1,
        learner_min_labels=40,
    )


@pytest.fixture
def fx_rates():
    return {"INR": 1.0, "USD": 86.0, "EUR": 93.0, "GBP": 108.0}
