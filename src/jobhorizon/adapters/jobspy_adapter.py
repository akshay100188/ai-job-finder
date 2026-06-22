from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.criteria import Criteria
from jobhorizon.logging_setup import get_logger
from jobhorizon.models import RawJob

logger = get_logger(__name__)
_TOS_PRINTED = False


def _print_tos_notice_once() -> None:
    global _TOS_PRINTED
    if _TOS_PRINTED:
        return
    print(
        "\n[jobspy] Tier B scraping enabled. Scraping may violate the source's terms "
        "of service; you are responsible for compliance in your jurisdiction.\n"
    )
    _TOS_PRINTED = True


class JobSpyAdapter(JobSourceAdapter):
    name = "jobspy"
    requires_key = False

    def __init__(self, sites: list[str], results_wanted: int = 25):
        self.sites = sites
        # LinkedIn is the most restrictive site - keep volume low regardless of config
        self.results_wanted = min(results_wanted, 10) if "linkedin" in sites else results_wanted

    def search(self, criteria: Criteria) -> list[RawJob]:
        _print_tos_notice_once()
        from jobspy import scrape_jobs  # imported lazily - only needed when Tier B is enabled

        out: list[RawJob] = []
        for title in criteria.titles or [""]:
            try:
                df = scrape_jobs(
                    site_name=self.sites,
                    search_term=title,
                    location=criteria.location,
                    results_wanted=self.results_wanted,
                    country_indeed="india",
                )
            except Exception as exc:
                logger.warning("jobspy scrape failed for '%s': %s", title, exc)
                continue
            for record in df.to_dict("records"):
                emails = record.get("emails") or []
                out.append(
                    RawJob(
                        source=str(record.get("site", self.name)),
                        title=record.get("title", ""),
                        company=record.get("company", ""),
                        location=record.get("location", ""),
                        url=record.get("job_url", ""),
                        external_id=str(record.get("id", "")) or None,
                        description=record.get("description", ""),
                        salary_min=record.get("min_amount"),
                        salary_max=record.get("max_amount"),
                        salary_currency=record.get("currency"),
                        posted_date=str(record.get("date_posted", "")) or None,
                        work_type_hint="remote" if record.get("is_remote") else None,
                        poster_email=emails[0] if emails else None,
                        raw={k: str(v) for k, v in record.items()},
                    )
                )
        return out
