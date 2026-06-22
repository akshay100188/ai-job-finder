import json
import sqlite3
from datetime import datetime, timezone

from jobhorizon.paths import DB_PATH, SCHEMA_PATH

KEPT_WHERE = "s.gate_passed = 1 AND s.score >= ? AND r.status != 'irrelevant'"
DISCARDED_WHERE = "(s.gate_passed = 0 OR s.score < ? OR r.status = 'irrelevant')"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- criteria -----------------------------------------------------------


def get_active_criteria(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM criteria WHERE active = 1 ORDER BY id DESC LIMIT 1").fetchone()


def insert_criteria(conn: sqlite3.Connection, row: dict) -> int:
    conn.execute("UPDATE criteria SET active = 0 WHERE active = 1")
    cur = conn.execute(
        """INSERT INTO criteria (titles, skills, location, working_mode, pay_min,
               pay_currency, score_threshold, created_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (
            row["titles"],
            row["skills"],
            row["location"],
            row["working_mode"],
            row["pay_min"],
            row["pay_currency"],
            row.get("score_threshold", 0.0),
            now_iso(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_score_threshold(conn: sqlite3.Connection, criteria_id: int, value: float) -> None:
    conn.execute("UPDATE criteria SET score_threshold = ? WHERE id = ?", (value, criteria_id))
    conn.commit()


# --- jobs -----------------------------------------------------------------


def upsert_job(conn: sqlite3.Connection, row: dict) -> bool:
    """Insert a new job or refresh an existing one. Returns True if the job is new."""
    existing = conn.execute("SELECT first_seen FROM jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
    ts = now_iso()
    if existing is None:
        conn.execute(
            """INSERT INTO jobs (
                   job_id, source, external_id, url, title, company, location,
                   work_type, description, salary_min, salary_max, salary_currency,
                   salary_min_inr, salary_max_inr, poster_name, poster_email,
                   posted_date, first_seen, last_seen, raw_json
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["job_id"],
                row["source"],
                row.get("external_id"),
                row.get("url"),
                row.get("title"),
                row.get("company"),
                row.get("location"),
                row.get("work_type"),
                row.get("description"),
                row.get("salary_min"),
                row.get("salary_max"),
                row.get("salary_currency"),
                row.get("salary_min_inr"),
                row.get("salary_max_inr"),
                row.get("poster_name"),
                row.get("poster_email"),
                row.get("posted_date"),
                ts,
                ts,
                row.get("raw_json"),
            ),
        )
        is_new = True
    else:
        conn.execute(
            """UPDATE jobs SET source=?, external_id=?, url=?, title=?, company=?,
                   location=?, work_type=?, description=?, salary_min=?, salary_max=?,
                   salary_currency=?, salary_min_inr=?, salary_max_inr=?, poster_name=?,
                   poster_email=?, posted_date=?, last_seen=?, raw_json=?
               WHERE job_id=?""",
            (
                row["source"],
                row.get("external_id"),
                row.get("url"),
                row.get("title"),
                row.get("company"),
                row.get("location"),
                row.get("work_type"),
                row.get("description"),
                row.get("salary_min"),
                row.get("salary_max"),
                row.get("salary_currency"),
                row.get("salary_min_inr"),
                row.get("salary_max_inr"),
                row.get("poster_name"),
                row.get("poster_email"),
                row.get("posted_date"),
                ts,
                row.get("raw_json"),
                row["job_id"],
            ),
        )
        is_new = False
    return is_new


def replace_job_score(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """INSERT INTO job_score (job_id, gate_passed, gate_reason, skills_matched,
               skills_matched_list, score, model_source)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(job_id) DO UPDATE SET
               gate_passed=excluded.gate_passed, gate_reason=excluded.gate_reason,
               skills_matched=excluded.skills_matched,
               skills_matched_list=excluded.skills_matched_list,
               score=excluded.score, model_source=excluded.model_source""",
        (
            row["job_id"],
            int(row["gate_passed"]),
            row.get("gate_reason"),
            row.get("skills_matched", 0),
            row.get("skills_matched_list"),
            row.get("score", 0.0),
            row.get("model_source", "deterministic"),
        ),
    )


def ensure_review_row(conn: sqlite3.Connection, job_id: str) -> None:
    conn.execute("INSERT OR IGNORE INTO review (job_id, status) VALUES (?, 'new')", (job_id,))


def update_review_status(conn: sqlite3.Connection, job_id: str, status: str, from_discard: bool) -> None:
    conn.execute(
        "UPDATE review SET status=?, reviewed_at=?, from_discard=? WHERE job_id=?",
        (status, now_iso(), int(from_discard), job_id),
    )
    conn.commit()


def get_review_status(conn: sqlite3.Connection, job_id: str) -> str | None:
    row = conn.execute("SELECT status FROM review WHERE job_id = ?", (job_id,)).fetchone()
    return row["status"] if row else None


def get_job_with_score(conn: sqlite3.Connection, job_id: str) -> dict | None:
    row = conn.execute(
        """SELECT j.*, s.skills_matched, s.skills_matched_list, s.score
           FROM jobs j JOIN job_score s ON j.job_id = s.job_id
           WHERE j.job_id = ?""",
        (job_id,),
    ).fetchone()
    return dict(row) if row else None


# --- dashboard reads --------------------------------------------------------


def _job_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["skills_matched_list"] = json.loads(d.get("skills_matched_list") or "[]")
    d["gate_passed"] = bool(d["gate_passed"])
    return d


def fetch_jobs_for_tab(conn: sqlite3.Connection, tab: str, threshold: float) -> list[dict]:
    where = KEPT_WHERE if tab == "kept" else DISCARDED_WHERE
    rows = conn.execute(
        f"""SELECT j.*, s.gate_passed, s.gate_reason, s.skills_matched, s.skills_matched_list,
                   s.score, s.model_source, r.status, r.from_discard
            FROM jobs j
            JOIN job_score s ON j.job_id = s.job_id
            JOIN review r ON j.job_id = r.job_id
            WHERE {where}
            ORDER BY s.score DESC""",
        (threshold,),
    ).fetchall()
    return [_job_dict(row) for row in rows]


def fetch_all_jobs_for_export(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT j.*, s.gate_passed, s.gate_reason, s.skills_matched, s.skills_matched_list,
                  s.score, s.model_source, r.status
           FROM jobs j
           JOIN job_score s ON j.job_id = s.job_id
           JOIN review r ON j.job_id = r.job_id
           ORDER BY s.score DESC"""
    ).fetchall()
    return [_job_dict(row) for row in rows]


# --- labels -------------------------------------------------------------------


def insert_label(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """INSERT INTO labels (labeled_at, relevant, from_discard, title, company, source,
               work_type, location, salary_min_inr, skills_matched, skills_matched_list,
               domain_hits, feature_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            now_iso(),
            int(row["relevant"]),
            int(row["from_discard"]),
            row.get("title"),
            row.get("company"),
            row.get("source"),
            row.get("work_type"),
            row.get("location"),
            row.get("salary_min_inr"),
            row.get("skills_matched"),
            row.get("skills_matched_list"),
            row.get("domain_hits"),
            row.get("feature_json"),
        ),
    )
    conn.commit()


# --- corpus lifecycle -------------------------------------------------------


def clear_corpus(conn: sqlite3.Connection, also_clear_labels: bool = False) -> None:
    conn.execute("DELETE FROM review")
    conn.execute("DELETE FROM job_score")
    conn.execute("DELETE FROM jobs")
    if also_clear_labels:
        conn.execute("DELETE FROM labels")
    conn.commit()


# --- tailored resumes (Phase 3) ----------------------------------------------


def insert_tailored_resume(conn: sqlite3.Connection, row: dict) -> int:
    cur = conn.execute(
        """INSERT INTO tailored_resumes (job_id, created_at, docx_path, md_path,
               gap_report_path, lint_status, lint_flags)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            row["job_id"],
            now_iso(),
            row.get("docx_path"),
            row.get("md_path"),
            row.get("gap_report_path"),
            row["lint_status"],
            row.get("lint_flags", "[]"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def fetch_tailored_resumes(conn: sqlite3.Connection, job_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM tailored_resumes WHERE job_id = ? ORDER BY id DESC", (job_id,)
    ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["lint_flags"] = json.loads(d.get("lint_flags") or "[]")
        results.append(d)
    return results


# --- runs -------------------------------------------------------------------


def log_run(
    conn: sqlite3.Connection,
    criteria_id: int | None,
    sources: list[str],
    n_fetched: int,
    n_new: int,
    n_gate_passed: int,
    notes: str = "",
) -> None:
    conn.execute(
        """INSERT INTO runs (ts, criteria_id, sources, n_fetched, n_new, n_gate_passed, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (now_iso(), criteria_id, ",".join(sources), n_fetched, n_new, n_gate_passed, notes),
    )
    conn.commit()
