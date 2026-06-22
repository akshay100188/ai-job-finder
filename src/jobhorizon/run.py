import argparse
import sys
from datetime import datetime, timezone

import pandas as pd

from jobhorizon import criteria as criteria_mod
from jobhorizon import db, learner
from jobhorizon.config import load_config
from jobhorizon.logging_setup import get_logger
from jobhorizon.paths import EXPORT_DIR
from jobhorizon.pipeline import run_pipeline

logger = get_logger(__name__)

EXPORT_COLUMNS = [
    "title",
    "company",
    "source",
    "location",
    "work_type",
    "score",
    "skills_matched",
    "skills_matched_list",
    "url",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_min_inr",
    "salary_max_inr",
    "posted_date",
]


def _export_csv(rows: list[dict]) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = EXPORT_DIR / f"run_{ts}.csv"
    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    df.to_csv(path, index=False)
    return str(path)


def _print_summary(result: dict) -> None:
    print(
        f"\nFetched {result['n_fetched']} | New {result['n_new']} | "
        f"Gate-passed {result['n_gate_passed']} | Sources: {', '.join(result['sources']) or '(none enabled)'}"
    )
    rows = sorted(result["new_gate_passed_rows"], key=lambda r: r["score"], reverse=True)
    if not rows:
        print("No new gate-passed jobs this run.")
        return
    print(f"\n{len(rows)} new gate-passed jobs:")
    for row in rows:
        print(
            f"  [{row['score']:.2f}] {row['title']} @ {row['company']} "
            f"({row['source']}, {row['work_type']}) - {row['url']}"
        )


def _print_learner_section(conn, criteria, app_config) -> None:
    n_labels = learner.count_labels(conn)
    min_labels = app_config.scoring.learner_min_labels
    print(f"\nLabels collected: {n_labels}/{min_labels}")

    report = learner.maybe_retrain_and_rescore(conn, criteria, app_config)
    if report is None:
        print("Below learner_min_labels - using deterministic scoring.")
    elif "error" in report:
        print(f"Learner not trained: {report['error']}")
    else:
        print("Learner retrained and rescored the current corpus. Top features:")
        for feat in report["top_features"]:
            print(f"  {feat['feature']}: {feat['weight']:+.4f}")

    metrics = learner.compute_metrics(conn)
    if metrics:
        precision = metrics["precision_at_k"]
        rescue_rate = metrics["discard_rescue_rate"]
        precision_str = f"{precision:.2f}" if precision is not None else "n/a"
        rescue_str = f"{rescue_rate:.2f}" if rescue_rate is not None else "n/a"
        print(f"precision@K: {precision_str} | discard-rescue rate: {rescue_str} (n={metrics['n_labels']})")

    hint = learner.rescue_hint(conn)
    if hint:
        print(f"Hint: {hint}")


def main() -> None:
    # Windows consoles default stdout/stderr to the system codepage (e.g. cp1252), which
    # can't encode many job titles/company names (accented characters, special dashes).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="JobHorizon daily pipeline")
    parser.add_argument(
        "--update-criteria",
        action="store_true",
        help="Clear current listings and re-prompt for criteria; keeps learned labels",
    )
    parser.add_argument(
        "--full-reset",
        action="store_true",
        help="Same as --update-criteria, but also clears learned label history",
    )
    args = parser.parse_args()

    conn = db.get_connection()
    db.init_db(conn)

    if args.full_reset or args.update_criteria:
        criteria = criteria_mod.update_criteria_flow(conn, full_reset=args.full_reset)
        if criteria is None:
            conn.close()
            return
    else:
        criteria = criteria_mod.ensure_criteria(conn)

    app_config = load_config()
    result = run_pipeline(conn, criteria, app_config)

    csv_path = _export_csv(result["new_gate_passed_rows"])
    print(f"\nCSV exported to {csv_path}")
    _print_summary(result)
    _print_learner_section(conn, criteria, app_config)

    conn.close()


if __name__ == "__main__":
    main()
