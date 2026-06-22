import json
import re

from jobhorizon.config import ScoringConfig
from jobhorizon.criteria import Criteria


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
    score = base_score + (scoring_cfg.domain_boost if domain_matched else 0.0)
    score = max(0.0, min(1.0, score))

    return {
        "skills_matched": len(matched),
        "skills_matched_list": json.dumps(matched),
        "score": score,
        "domain_hits": len(domain_matched),
        "domain_matched_list": json.dumps(domain_matched),
    }
