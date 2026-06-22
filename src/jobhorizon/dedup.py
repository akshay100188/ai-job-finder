import hashlib
import re
import sqlite3

from jobhorizon import db


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def compute_job_id(company: str, title: str, location: str) -> str:
    key = f"{_norm(company)}|{_norm(title)}|{_norm(location)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def dedup_and_upsert(conn: sqlite3.Connection, job_row: dict) -> tuple[str, bool]:
    """Cross-source dedup (same job from two sources) and temporal dedup (seen
    yesterday) both fall out of hashing on (company, title, location)."""
    job_id = compute_job_id(job_row.get("company", ""), job_row.get("title", ""), job_row.get("location", ""))
    job_row = dict(job_row, job_id=job_id)
    is_new = db.upsert_job(conn, job_row)
    return job_id, is_new
