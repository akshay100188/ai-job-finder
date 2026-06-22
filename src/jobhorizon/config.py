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
    domain_boost: float = 0.1
    title_boost: float = 0.3
    domain_as_gate: bool = False
    learner_min_labels: int = 40


@dataclass
class TailoringConfig:
    model_extract: str = "claude-haiku-4-5-20251001"
    model_rephrase: str = "claude-sonnet-4-6"
    include_tailored_summary: bool = True
    output_formats: list[str] = field(default_factory=lambda: ["docx", "md"])
    run_lint_llm_pass: bool = True


@dataclass
class Secrets:
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_key: str = ""
    anthropic_api_key: str = ""


@dataclass
class AppConfig:
    sources: dict
    filter: FilterConfig
    scoring: ScoringConfig
    fx_rates_to_inr: dict
    secrets: Secrets
    tailoring: TailoringConfig = field(default_factory=TailoringConfig)


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
        domain_boost=scoring_raw.get("domain_boost", 0.1),
        title_boost=scoring_raw.get("title_boost", 0.3),
        domain_as_gate=scoring_raw.get("domain_as_gate", False),
        learner_min_labels=scoring_raw.get("learner_min_labels", 40),
    )

    tailoring_raw = raw.get("tailoring", {})
    tailoring_cfg = TailoringConfig(
        model_extract=tailoring_raw.get("model_extract", "claude-haiku-4-5-20251001"),
        model_rephrase=tailoring_raw.get("model_rephrase", "claude-sonnet-4-6"),
        include_tailored_summary=tailoring_raw.get("include_tailored_summary", True),
        output_formats=tailoring_raw.get("output_formats", ["docx", "md"]) or ["docx", "md"],
        run_lint_llm_pass=tailoring_raw.get("run_lint_llm_pass", True),
    )

    secrets = Secrets(
        adzuna_app_id=os.environ.get("ADZUNA_APP_ID", ""),
        adzuna_app_key=os.environ.get("ADZUNA_APP_KEY", ""),
        jooble_key=os.environ.get("JOOBLE_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
    )

    return AppConfig(
        sources=raw.get("sources", {}),
        filter=filter_cfg,
        scoring=scoring_cfg,
        tailoring=tailoring_cfg,
        fx_rates_to_inr=raw.get("fx_rates_to_inr", {"INR": 1.0}),
        secrets=secrets,
    )
