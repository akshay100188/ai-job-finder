from jobhorizon.config import FilterConfig
from jobhorizon.criteria import Criteria


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _location_gate(location: str | None, accept: list[str], reject: list[str]) -> tuple[bool, str]:
    loc = _norm(location)
    if not loc:
        return True, "passed_ambiguous_location"
    for alias in reject:
        if alias in loc:
            return False, "location_rejected"
    return True, "passed"


def evaluate_gates(
    job_row: dict, criteria: Criteria, filter_cfg: FilterConfig, fx_rates: dict
) -> tuple[bool, str]:
    # pay gate
    salary_max_inr = job_row.get("salary_max_inr")
    pay_min_rate = fx_rates.get((criteria.pay_currency or "INR").upper())
    pay_min_inr = criteria.pay_min * pay_min_rate if pay_min_rate is not None else None
    if salary_max_inr is not None and pay_min_inr is not None and salary_max_inr < pay_min_inr:
        return False, "pay_below_minimum"

    # mode gate
    work_type = job_row.get("work_type") or "unknown"
    mode = criteria.working_mode

    if mode == "remote":
        if work_type not in ("remote", "unknown"):
            return False, "mode_not_remote"
        return True, "passed"

    if mode == "hybrid":
        if work_type not in ("hybrid", "unknown"):
            return False, "mode_not_hybrid"
        loc_passed, loc_reason = _location_gate(
            job_row.get("location"),
            filter_cfg.location_aliases.accept,
            filter_cfg.location_aliases.reject,
        )
        if not loc_passed:
            return False, loc_reason
        return True, "passed"

    # mode == "any" (or unrecognized -> recall bias, pass)
    return True, "passed"
