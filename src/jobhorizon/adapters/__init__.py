from abc import ABC, abstractmethod

from jobhorizon.criteria import Criteria
from jobhorizon.logging_setup import get_logger
from jobhorizon.models import RawJob

logger = get_logger(__name__)


class JobSourceAdapter(ABC):
    name: str = ""
    requires_key: bool = False

    @abstractmethod
    def search(self, criteria: Criteria) -> list[RawJob]: ...


def build_adapters(app_config) -> list[JobSourceAdapter]:
    sources = app_config.sources
    secrets = app_config.secrets
    adapters: list[JobSourceAdapter] = []

    def enabled(key: str) -> bool:
        return bool(sources.get(key, {}).get("enabled"))

    if enabled("adzuna"):
        if secrets.adzuna_app_id and secrets.adzuna_app_key:
            from jobhorizon.adapters.adzuna import AdzunaAdapter

            adapters.append(
                AdzunaAdapter(
                    app_id=secrets.adzuna_app_id,
                    app_key=secrets.adzuna_app_key,
                    country=sources["adzuna"].get("country", "in"),
                )
            )
        else:
            logger.warning("adzuna enabled but ADZUNA_APP_ID/ADZUNA_APP_KEY missing in .env - skipping")

    if enabled("jooble"):
        if secrets.jooble_key:
            from jobhorizon.adapters.jooble import JoobleAdapter

            adapters.append(JoobleAdapter(api_key=secrets.jooble_key))
        else:
            logger.warning("jooble enabled but JOOBLE_KEY missing in .env - skipping")

    if enabled("remoteok"):
        from jobhorizon.adapters.remoteok import RemoteOKAdapter

        adapters.append(RemoteOKAdapter())

    if enabled("himalayas"):
        from jobhorizon.adapters.himalayas import HimalayasAdapter

        adapters.append(HimalayasAdapter())

    if enabled("remotive"):
        from jobhorizon.adapters.remotive import RemotiveAdapter

        adapters.append(RemotiveAdapter())

    if enabled("arbeitnow"):
        from jobhorizon.adapters.arbeitnow import ArbeitnowAdapter

        adapters.append(ArbeitnowAdapter())

    if enabled("jobicy"):
        from jobhorizon.adapters.jobicy import JobicyAdapter

        adapters.append(JobicyAdapter())

    if enabled("wwr"):
        from jobhorizon.adapters.wwr import WWRAdapter

        adapters.append(WWRAdapter(categories=sources["wwr"].get("categories", ["remote-jobs"])))

    if enabled("jobspy"):
        from jobhorizon.adapters.jobspy_adapter import JobSpyAdapter

        adapters.append(
            JobSpyAdapter(
                sites=sources["jobspy"].get("sites", ["indeed"]),
                results_wanted=sources["jobspy"].get("results_wanted", 25),
            )
        )

    return adapters
