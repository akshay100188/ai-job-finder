from jobhorizon.dedup import compute_job_id, dedup_and_upsert


def test_compute_job_id_is_stable_and_case_insensitive():
    a = compute_job_id("Acme Corp", "Backend Engineer", "Noida")
    b = compute_job_id("acme corp", "backend engineer", "noida")
    assert a == b


def test_compute_job_id_differs_for_different_jobs():
    a = compute_job_id("Acme Corp", "Backend Engineer", "Noida")
    b = compute_job_id("Acme Corp", "Frontend Engineer", "Noida")
    assert a != b


def _job_row(**overrides):
    row = {
        "source": "remoteok",
        "external_id": "1",
        "url": "http://x",
        "title": "Backend Engineer",
        "company": "Acme Corp",
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
    row.update(overrides)
    return row


def test_new_job_is_inserted_as_new(conn):
    job_id, is_new = dedup_and_upsert(conn, _job_row())
    assert is_new is True
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    assert row["first_seen"] == row["last_seen"]


def test_cross_source_same_job_dedupes(conn):
    id1, new1 = dedup_and_upsert(conn, _job_row(source="remoteok"))
    id2, new2 = dedup_and_upsert(conn, _job_row(source="naukri"))
    assert id1 == id2
    assert new1 is True
    assert new2 is False
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (id1,)).fetchone()
    assert row["source"] == "naukri"  # refreshed to latest seen
    assert conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"] == 1


def test_seen_again_bumps_last_seen_keeps_first_seen(conn):
    job_id, _ = dedup_and_upsert(conn, _job_row())
    first_row = conn.execute("SELECT first_seen, last_seen FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    _, is_new = dedup_and_upsert(conn, _job_row())
    second_row = conn.execute("SELECT first_seen, last_seen FROM jobs WHERE job_id=?", (job_id,)).fetchone()
    assert is_new is False
    assert second_row["first_seen"] == first_row["first_seen"]
