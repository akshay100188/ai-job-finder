import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

from jobhorizon.paths import CONFIG_PATH, ENV_PATH


@dataclass
class LocationAliases:
    accept: list[str] = field(default_factory=list)
    reject: list[str] = field(default_factory=list)


@dataclass
class FilterConfig:
    recall_bias: bool = True
    location_aliases: LocationAliases = field(default_factory=LocationAliases)
    recency_days: int = 30


@dataclass
class ScoringConfig:
    skill_weights: dict = field(default_factory=dict)
    domain_keywords: list[str] = field(default_factory=list)
    domain_boost: float = 0.1
    learner_min_labels: int = 40


@dataclass
class Secrets:
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_key: str = ""


@dataclass
class AppConfig:
    sources: dict
    filter: FilterConfig
    scoring: ScoringConfig
    fx_rates_to_inr: dict
    secrets: Secrets


def load_config() -> AppConfig:
    load_dotenv(ENV_PATH)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    filter_raw = raw.get("filter", {})
    aliases_raw = filter_raw.get("location_aliases", {})
    filter_cfg = FilterConfig(
        recall_bias=filter_raw.get("recall_bias", True),
        location_aliases=LocationAliases(
            accept=[a.lower() for a in aliases_raw.get("accept", [])],
            reject=[r.lower() for r in aliases_raw.get("reject", [])],
        ),
        recency_days=filter_raw.get("recency_days", 30),
    )

    scoring_raw = raw.get("scoring", {})
    scoring_cfg = ScoringConfig(
        skill_weights=scoring_raw.get("skill_weights", {}) or {},
        domain_keywords=scoring_raw.get("domain_keywords", []) or [],
        domain_boost=scoring_raw.get("domain_boost", 0.1),
        learner_min_labels=scoring_raw.get("learner_min_labels", 40),
    )

    secrets = Secrets(
        adzuna_app_id=os.environ.get("ADZUNA_APP_ID", ""),
        adzuna_app_key=os.environ.get("ADZUNA_APP_KEY", ""),
        jooble_key=os.environ.get("JOOBLE_KEY", ""),
    )

    return AppConfig(
        sources=raw.get("sources", {}),
        filter=filter_cfg,
        scoring=scoring_cfg,
        fx_rates_to_inr=raw.get("fx_rates_to_inr", {"INR": 1.0}),
        secrets=secrets,
    )
