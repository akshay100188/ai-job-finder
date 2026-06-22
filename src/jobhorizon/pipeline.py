import sqlite3

from jobhorizon import db
from jobhorizon.adapters import build_adapters
from jobhorizon.config import AppConfig
from jobhorizon.criteria import Criteria
from jobhorizon.dedup import dedup_and_upsert
from jobhorizon.filters import evaluate_gates
from jobhorizon.logging_setup import get_logger
from jobhorizon.normalize import normalize_job
from jobhorizon.scoring import score_job

logger = get_logger(__name__)


def run_pipeline(conn: sqlite3.Connection, criteria: Criteria, app_config: AppConfig) -> dict:
    adapters = build_adapters(app_config)
    raw_jobs = []
    source_names = []
    for adapter in adapters:
        source_names.append(adapter.name)
        try:
            jobs = adapter.search(criteria)
        except Exception as exc:
            logger.warning("adapter %s failed: %s", adapter.name, exc)
            jobs = []
        logger.info("%s: fetched %d raw jobs", adapter.name, len(jobs))
        raw_jobs.extend(jobs)

    n_fetched = len(raw_jobs)
    n_new = 0
    n_gate_passed = 0
    new_gate_passed_rows = []

    for raw in raw_jobs:
        job_row = normalize_job(raw, app_config.fx_rates_to_inr)
        job_id, is_new = dedup_and_upsert(conn, job_row)
        job_row["job_id"] = job_id
        if is_new:
            n_new += 1

        gate_passed, gate_reason = evaluate_gates(
            job_row, criteria, app_config.filter, app_config.fx_rates_to_inr
        )
        score_result = score_job(job_row, criteria, app_config.scoring)
        db.replace_job_score(
            conn,
            {
                "job_id": job_id,
                "gate_passed": gate_passed,
                "gate_reason": gate_reason,
                **score_result,
                "model_source": "deterministic",
            },
        )
        db.ensure_review_row(conn, job_id)

        if gate_passed:
            n_gate_passed += 1
            if is_new:
                new_gate_passed_rows.append({**job_row, **score_result, "gate_reason": gate_reason})

    conn.commit()
    db.log_run(conn, criteria.id, source_names, n_fetched, n_new, n_gate_passed)

    return {
        "n_fetched": n_fetched,
        "n_new": n_new,
        "n_gate_passed": n_gate_passed,
        "new_gate_passed_rows": new_gate_passed_rows,
        "sources": source_names,
    }
