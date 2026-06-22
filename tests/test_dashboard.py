import json

import pytest

from jobhorizon import db
from jobhorizon.dashboard import create_app


@pytest.fixture
def client(conn):
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _seed_criteria(conn, score_threshold: float = 0.3) -> int:
    return db.insert_criteria(
        conn,
        {
            "titles": json.dumps(["Backend Engineer"]),
            "skills": json.dumps(["Python"]),
            "location": "Noida",
            "working_mode": "hybrid",
            "pay_min": 1000000,
            "pay_currency": "INR",
            "score_threshold": score_threshold,
        },
    )


def _seed_job(conn, job_id, score, gate_passed=True, status="new", from_discard=False, **overrides):
    job = {
        "job_id": job_id,
        "source": "remoteok",
        "external_id": "1",
        "url": "http://x",
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Noida",
        "work_type": "hybrid",
        "description": "",
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_min_inr": None,
        "salary_max_inr": None,
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
            "job_id": job_id,
            "gate_passed": gate_passed,
            "gate_reason": "passed",
            "skills_matched": 1,
            "skills_matched_list": '["Python"]',
            "score": score,
            "model_source": "deterministic",
        },
    )
    db.ensure_review_row(conn, job_id)
    if status != "new" or from_discard:
        db.update_review_status(conn, job_id, status, from_discard)
    conn.commit()


def test_api_jobs_kept_and_discarded_partition(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.8, gate_passed=True)  # kept
    _seed_job(conn, "j2", score=0.1, gate_passed=True)  # below threshold
    _seed_job(conn, "j3", score=0.9, gate_passed=False)  # gate failed
    _seed_job(conn, "j4", score=0.9, gate_passed=True, status="irrelevant")  # marked irrelevant

    kept = {j["job_id"] for j in client.get("/api/jobs?tab=kept&threshold=0.3").get_json()}
    discarded = {j["job_id"] for j in client.get("/api/jobs?tab=discarded&threshold=0.3").get_json()}

    assert kept == {"j1"}
    assert discarded == {"j2", "j3", "j4"}


def test_api_jobs_score_equal_to_threshold_is_kept(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.3, gate_passed=True)
    kept = {j["job_id"] for j in client.get("/api/jobs?tab=kept&threshold=0.3").get_json()}
    assert kept == {"j1"}


def test_api_jobs_rejects_bad_tab(client, conn):
    _seed_criteria(conn)
    res = client.get("/api/jobs?tab=bogus")
    assert res.status_code == 400


def test_api_mark_updates_review_and_appends_label(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.8, gate_passed=True)

    res = client.post("/api/mark", json={"job_id": "j1", "relevant": True, "from_discard": False})

    assert res.status_code == 200
    review_row = conn.execute("SELECT status, from_discard FROM review WHERE job_id='j1'").fetchone()
    assert review_row["status"] == "relevant"
    assert review_row["from_discard"] == 0
    label_row = conn.execute("SELECT relevant FROM labels").fetchone()
    assert label_row["relevant"] == 1


def test_api_mark_unknown_job_returns_404(client, conn):
    _seed_criteria(conn)
    res = client.post("/api/mark", json={"job_id": "nope", "relevant": True})
    assert res.status_code == 404


def test_api_threshold_persists_to_active_criteria(client, conn):
    criteria_id = _seed_criteria(conn)
    res = client.post("/api/threshold", json={"value": 0.55})
    assert res.status_code == 200
    row = conn.execute("SELECT score_threshold FROM criteria WHERE id=?", (criteria_id,)).fetchone()
    assert row["score_threshold"] == 0.55


def test_api_update_criteria_requires_confirm_when_criteria_exists(client, conn):
    _seed_criteria(conn)
    res = client.post(
        "/api/update-criteria",
        json={
            "titles": ["X"],
            "skills": [],
            "location": "",
            "working_mode": "any",
            "pay_min": 0,
            "pay_currency": "INR",
        },
    )
    assert res.status_code == 400


def test_api_update_criteria_clears_corpus_but_keeps_labels(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.8, gate_passed=True)
    client.post("/api/mark", json={"job_id": "j1", "relevant": True, "from_discard": False})
    assert conn.execute("SELECT COUNT(*) c FROM labels").fetchone()["c"] == 1

    res = client.post(
        "/api/update-criteria",
        json={
            "confirm": True,
            "titles": ["New Title"],
            "skills": ["Go"],
            "location": "Pune",
            "working_mode": "remote",
            "pay_min": 2000000,
            "pay_currency": "INR",
        },
    )

    assert res.status_code == 200
    assert conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 0
    assert conn.execute("SELECT COUNT(*) c FROM labels").fetchone()["c"] == 1
    new_criteria = conn.execute("SELECT * FROM criteria WHERE active=1").fetchone()
    assert json.loads(new_criteria["titles"]) == ["New Title"]


def test_api_update_criteria_full_reset_clears_labels_too(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.8, gate_passed=True)
    client.post("/api/mark", json={"job_id": "j1", "relevant": True, "from_discard": False})

    res = client.post(
        "/api/update-criteria",
        json={
            "confirm": True,
            "full_reset": True,
            "titles": ["New"],
            "skills": [],
            "location": "",
            "working_mode": "any",
            "pay_min": 0,
            "pay_currency": "INR",
        },
    )

    assert res.status_code == 200
    assert conn.execute("SELECT COUNT(*) c FROM labels").fetchone()["c"] == 0


def test_api_export_csv_returns_csv_content_type(client, conn):
    _seed_criteria(conn)
    _seed_job(conn, "j1", score=0.8, gate_passed=True)
    res = client.get("/api/export.csv")
    assert res.status_code == 200
    assert res.mimetype == "text/csv"
    assert "j1" in res.get_data(as_text=True)
