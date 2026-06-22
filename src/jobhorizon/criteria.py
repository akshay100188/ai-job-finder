import json
import sqlite3
from dataclasses import dataclass

from jobhorizon import db


@dataclass
class Criteria:
    titles: list[str]
    skills: list[str]
    location: str
    working_mode: str  # remote | hybrid | any
    pay_min: float
    pay_currency: str
    score_threshold: float = 0.0
    id: int | None = None

    @staticmethod
    def from_row(row: sqlite3.Row) -> "Criteria":
        return Criteria(
            titles=json.loads(row["titles"] or "[]"),
            skills=json.loads(row["skills"] or "[]"),
            location=row["location"],
            working_mode=row["working_mode"],
            pay_min=row["pay_min"],
            pay_currency=row["pay_currency"],
            score_threshold=row["score_threshold"],
            id=row["id"],
        )


def load_active_criteria(conn: sqlite3.Connection) -> Criteria | None:
    row = db.get_active_criteria(conn)
    return Criteria.from_row(row) if row else None


def save_criteria(conn: sqlite3.Connection, criteria: Criteria) -> Criteria:
    new_id = db.insert_criteria(
        conn,
        {
            "titles": json.dumps(criteria.titles),
            "skills": json.dumps(criteria.skills),
            "location": criteria.location,
            "working_mode": criteria.working_mode,
            "pay_min": criteria.pay_min,
            "pay_currency": criteria.pay_currency,
            "score_threshold": criteria.score_threshold,
        },
    )
    criteria.id = new_id
    return criteria


def _prompt_list(label: str, max_items: int | None = None) -> list[str]:
    raw = input(f"{label} (comma-separated): ").strip()
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items[:max_items] if max_items else items


def prompt_criteria_cli() -> Criteria:
    print("\n--- JobHorizon setup ---")
    titles = _prompt_list("Job titles you're targeting (up to 5)", max_items=5)
    skills = _prompt_list("Skills to match against listings")
    location = input("Location (e.g. 'Noida'): ").strip()
    working_mode = ""
    while working_mode not in ("remote", "hybrid", "any"):
        working_mode = input("Working mode [remote/hybrid/any]: ").strip().lower()
    pay_min = float(input("Minimum acceptable pay: ").strip())
    pay_currency = input("Pay currency (e.g. INR, USD): ").strip().upper()
    return Criteria(
        titles=titles,
        skills=skills,
        location=location,
        working_mode=working_mode,
        pay_min=pay_min,
        pay_currency=pay_currency,
    )


def ensure_criteria(conn: sqlite3.Connection) -> Criteria:
    existing = load_active_criteria(conn)
    if existing:
        return existing
    criteria = prompt_criteria_cli()
    return save_criteria(conn, criteria)


def update_criteria_flow(conn: sqlite3.Connection, full_reset: bool = False) -> Criteria | None:
    print(
        "\nUpdating criteria clears your current listings and starts a fresh search. "
        + (
            "Your learned preferences will ALSO be cleared (--full-reset)."
            if full_reset
            else "Your learned preferences are kept."
        )
    )
    confirm = input("Proceed? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return None
    db.clear_corpus(conn, also_clear_labels=full_reset)
    criteria = prompt_criteria_cli()
    return save_criteria(conn, criteria)
