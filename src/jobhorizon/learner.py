import json
import sqlite3
from collections import Counter

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from jobhorizon import db
from jobhorizon.config import AppConfig, LocationAliases
from jobhorizon.criteria import Criteria
from jobhorizon.features import extract_feature_dict
from jobhorizon.logging_setup import get_logger

logger = get_logger(__name__)

# Discard-tab rescues (from_discard=1, relevant=1) are the strongest false-drop
# signal per the brief -- weight them 2x in training.
RESCUE_SAMPLE_WEIGHT = 2.0
TOP_N_FEATURES = 10
CATEGORICAL_COLUMNS = ["source", "work_type", "salary_band"]
PASSTHROUGH_COLUMNS = ["skills_matched", "domain_hits", "location_match"]


def count_labels(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) c FROM labels").fetchone()["c"]


def _load_label_features(conn: sqlite3.Connection) -> tuple[list[dict], list[int], list[float]]:
    rows = conn.execute("SELECT feature_json, relevant, from_discard FROM labels").fetchall()
    features, targets, weights = [], [], []
    for row in rows:
        features.append(json.loads(row["feature_json"]))
        targets.append(int(row["relevant"]))
        is_rescue = bool(row["from_discard"]) and bool(row["relevant"])
        weights.append(RESCUE_SAMPLE_WEIGHT if is_rescue else 1.0)
    return features, targets, weights


def _to_frame(feature_dicts: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(feature_dicts)
    df["location_match"] = df["location_match"].astype(int)
    return df


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            ("title", CountVectorizer(max_features=200, stop_words="english"), "title"),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_COLUMNS),
        ],
        remainder="passthrough",  # passes through PASSTHROUGH_COLUMNS unchanged
    )
    return Pipeline([("pre", preprocessor), ("clf", LogisticRegression(max_iter=1000))])


def _build_report(pipeline: Pipeline, n_labels: int) -> dict:
    pre = pipeline.named_steps["pre"]
    clf = pipeline.named_steps["clf"]
    feature_names = list(pre.get_feature_names_out())
    coefs = clf.coef_[0]
    pairs = sorted(zip(feature_names, coefs, strict=True), key=lambda p: abs(p[1]), reverse=True)[
        :TOP_N_FEATURES
    ]
    return {
        "n_labels": n_labels,
        "top_features": [{"feature": name, "weight": round(float(weight), 4)} for name, weight in pairs],
    }


def train_model(conn: sqlite3.Connection) -> tuple[Pipeline | None, dict]:
    features, targets, weights = _load_label_features(conn)
    if len(set(targets)) < 2:
        return None, {
            "n_labels": len(features),
            "error": "need both relevant and irrelevant labels to train",
        }
    df = _to_frame(features)
    pipeline = _build_pipeline()
    pipeline.fit(df, targets, clf__sample_weight=weights)
    return pipeline, _build_report(pipeline, len(features))


def score_with_learner(
    pipeline: Pipeline,
    job_rows: list[dict],
    domain_keywords: list[str],
    location_aliases: LocationAliases,
) -> list[float]:
    feature_dicts = [extract_feature_dict(row, domain_keywords, location_aliases) for row in job_rows]
    df = _to_frame(feature_dicts)
    probs = pipeline.predict_proba(df)
    classes = list(pipeline.classes_)
    relevant_idx = classes.index(1) if 1 in classes else 0
    return [float(max(0.0, min(1.0, p))) for p in probs[:, relevant_idx]]


def maybe_retrain_and_rescore(
    conn: sqlite3.Connection, criteria: Criteria, app_config: AppConfig
) -> dict | None:
    if count_labels(conn) < app_config.scoring.learner_min_labels:
        return None

    pipeline, report = train_model(conn)
    if pipeline is None:
        return report

    job_rows = db.fetch_all_jobs_for_export(conn)
    if job_rows:
        scores = score_with_learner(
            pipeline, job_rows, criteria.domain_keywords, app_config.filter.location_aliases
        )
        for row, score in zip(job_rows, scores, strict=True):
            db.replace_job_score(
                conn,
                {
                    "job_id": row["job_id"],
                    "gate_passed": row["gate_passed"],
                    "gate_reason": row["gate_reason"],
                    "skills_matched": row["skills_matched"],
                    "skills_matched_list": json.dumps(row["skills_matched_list"]),
                    "score": score,
                    "model_source": "learner",
                },
            )
        conn.commit()

    return report


def compute_metrics(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT from_discard, relevant FROM labels").fetchall()
    if not rows:
        return {}
    non_discard = [r["relevant"] for r in rows if not r["from_discard"]]
    discard = [r["relevant"] for r in rows if r["from_discard"]]
    return {
        "n_labels": len(rows),
        "precision_at_k": (sum(non_discard) / len(non_discard)) if non_discard else None,
        "discard_rescue_rate": (sum(discard) / len(discard)) if discard else None,
    }


def rescue_hint(conn: sqlite3.Connection) -> str | None:
    rows = conn.execute(
        "SELECT source, location FROM labels WHERE from_discard = 1 AND relevant = 1"
    ).fetchall()
    if not rows:
        return None

    sources = Counter(r["source"] for r in rows if r["source"])
    locations = Counter((r["location"] or "").strip().lower() for r in rows if r["location"])

    hints = [
        f"{count} discard-rescues share source={name} - consider its gate settings"
        for name, count in sources.items()
        if count >= 2
    ] + [
        f"{count} discard-rescues share location={name} - consider its gate settings"
        for name, count in locations.items()
        if count >= 2
    ]
    return "; ".join(hints) if hints else None
