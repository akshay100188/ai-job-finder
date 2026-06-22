import json
import re

from jobhorizon.models import RawJob

_WORK_TYPE_PATTERNS = {
    "remote": re.compile(r"\bremote\b", re.IGNORECASE),
    "hybrid": re.compile(r"\bhybrid\b", re.IGNORECASE),
    "onsite": re.compile(r"\b(on[\s-]?site|in[\s-]?office)\b", re.IGNORECASE),
}


def _parse_work_type(raw: RawJob) -> str:
    if raw.work_type_hint in ("remote", "hybrid", "onsite"):
        return raw.work_type_hint
    text = f"{raw.title} {raw.description}"
    hits = {kind for kind, pattern in _WORK_TYPE_PATTERNS.items() if pattern.search(text)}
    return hits.pop() if len(hits) == 1 else "unknown"


def _to_inr(amount: float | None, currency: str | None, fx_rates: dict) -> float | None:
    if amount is None or not currency:
        return None
    rate = fx_rates.get(currency.upper())
    if rate is None:
        return None  # unknown currency -> can't convert -> leave null (recall bias)
    return amount * rate


def normalize_job(raw: RawJob, fx_rates: dict) -> dict:
    return {
        "source": raw.source,
        "external_id": raw.external_id,
        "url": raw.url,
        "title": raw.title,
        "company": raw.company,
        "location": raw.location,
        "work_type": _parse_work_type(raw),
        "description": raw.description,
        "salary_min": raw.salary_min,
        "salary_max": raw.salary_max,
        "salary_currency": raw.salary_currency,
        "salary_min_inr": _to_inr(raw.salary_min, raw.salary_currency, fx_rates),
        "salary_max_inr": _to_inr(raw.salary_max, raw.salary_currency, fx_rates),
        "poster_name": raw.poster_name,
        "poster_email": raw.poster_email,
        "posted_date": raw.posted_date,
        "raw_json": json.dumps(raw.raw, default=str),
    }
