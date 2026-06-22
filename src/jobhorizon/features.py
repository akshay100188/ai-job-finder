import json
import re
import sqlite3

from jobhorizon import criteria as criteria_mod
from jobhorizon import db
from jobhorizon.config import AppConfig, LocationAliases

# Fixed INR (lakh) buckets for the learner's salary feature -- a deliberate
# simplification per the brief ("keep features simple to avoid overfitting").
_SALARY_BANDS = [
    (500_000, "<5L"),
    (1_000_000, "5-10L"),
    (2_000_000, "10-20L"),
    (3_000_000, "20-30L"),
]


def _salary_band(salary_min_inr: float | None) -> str:
    if salary_min_inr is None:
        return "unknown"
    for ceiling, label in _SALARY_BANDS:
        if salary_min_inr < ceiling:
            return label
    return "30L+"


def _count_domain_hits(text: str, domain_keywords: list[str]) -> int:
    t = text.lower()
    return sum(1 for kw in domain_keywords if re.search(r"\b" + re.escape(kw.lower()) + r"\b", t))


def _location_match(location: str | None, accept_aliases: list[str]) -> bool:
    loc = (location or "").strip().lower()
    return any(alias in loc for alias in accept_aliases)


def extract_feature_dict(
    job_row: dict, domain_keywords: list[str], location_aliases: LocationAliases
) -> dict:
    text = f"{job_row.get('title', '')} {job_row.get('description', '')}"
    return {
        "title": job_row.get("title", ""),
        "skills_matched": job_row.get("skills_matched", 0),
        "domain_hits": _count_domain_hits(text, domain_keywords),
        "source": job_row.get("source", ""),
        "work_type": job_row.get("work_type", "unknown"),
        "salary_band": _salary_band(job_row.get("salary_min_inr")),
        "location_match": _location_match(job_row.get("location"), location_aliases.accept),
    }


def record_label(
    conn: sqlite3.Connection, job_id: str, relevant: bool, from_discard: bool, app_config: AppConfig
) -> None:
    job_row = db.get_job_with_score(conn, job_id)
    if job_row is None:
        raise ValueError(f"unknown job_id: {job_id}")

    criteria = criteria_mod.load_active_criteria(conn)
    domain_keywords = criteria.domain_keywords if criteria else []
    feature_dict = extract_feature_dict(job_row, domain_keywords, app_config.filter.location_aliases)
    db.insert_label(
        conn,
        {
            "relevant": relevant,
            "from_discard": from_discard,
            "title": job_row.get("title"),
            "company": job_row.get("company"),
            "source": job_row.get("source"),
            "work_type": job_row.get("work_type"),
            "location": job_row.get("location"),
            "salary_min_inr": job_row.get("salary_min_inr"),
            "skills_matched": job_row.get("skills_matched"),
            "skills_matched_list": job_row.get("skills_matched_list"),
            "domain_hits": feature_dict["domain_hits"],
            "feature_json": json.dumps(feature_dict),
        },
    )
