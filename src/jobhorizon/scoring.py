import json
import re

from jobhorizon.config import ScoringConfig
from jobhorizon.criteria import Criteria


def _title_matches(job_title: str, criteria_titles: list[str]) -> bool:
    """A job title is considered relevant if it shares most of its words with one of
    the titles the user is actually searching for -- catches variants like "AI Agent
    Product Manager" matching criteria title "AI Product Manager" without requiring an
    exact phrase match."""
    job_words = set(re.findall(r"\w+", job_title.lower()))
    for title in criteria_titles:
        words = re.findall(r"\w+", title.lower())
        if not words:
            continue
        overlap = sum(1 for w in words if w in job_words)
        if overlap / len(words) >= 0.66:
            return True
    return False


def score_job(job_row: dict, criteria: Criteria, scoring_cfg: ScoringConfig) -> dict:
    text = f"{job_row.get('title', '')} {job_row.get('description', '')}".lower()

    matched = []
    total_weight = 0.0
    matched_weight = 0.0
    for skill in criteria.skills:
        weight = scoring_cfg.skill_weights.get(skill, 1.0)
        total_weight += weight
        if re.search(r"\b" + re.escape(skill.lower()) + r"\b", text):
            matched.append(skill)
            matched_weight += weight

    base_score = (matched_weight / total_weight) if total_weight > 0 else 0.0
    domain_matched = [
        kw for kw in criteria.domain_keywords if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text)
    ]
    title_hit = _title_matches(job_row.get("title", ""), criteria.titles)
    score = (
        base_score
        + (scoring_cfg.domain_boost if domain_matched else 0.0)
        + (scoring_cfg.title_boost if title_hit else 0.0)
    )
    score = max(0.0, min(1.0, score))

    return {
        "skills_matched": len(matched),
        "skills_matched_list": json.dumps(matched),
        "score": score,
        "domain_hits": len(domain_matched),
        "domain_matched_list": json.dumps(domain_matched),
    }
