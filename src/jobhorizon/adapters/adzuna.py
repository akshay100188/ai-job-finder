from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob

COUNTRY_CURRENCY = {
    "in": "INR",
    "us": "USD",
    "gb": "GBP",
    "au": "AUD",
    "ca": "CAD",
    "de": "EUR",
    "fr": "EUR",
    "nl": "EUR",
    "sg": "SGD",
    "nz": "NZD",
    "za": "ZAR",
    "br": "BRL",
}


class AdzunaAdapter(JobSourceAdapter):
    name = "adzuna"
    requires_key = True

    def __init__(self, app_id: str, app_key: str, country: str = "in"):
        self.app_id = app_id
        self.app_key = app_key
        self.country = country

    def search(self, criteria: Criteria) -> list[RawJob]:
        currency = COUNTRY_CURRENCY.get(self.country, "INR")
        out: list[RawJob] = []
        for title in criteria.titles or [""]:
            url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1"
            params = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": 25,
                "what": title,
                "content-type": "application/json",
            }
            if criteria.location and criteria.working_mode != "remote":
                params["where"] = criteria.location
            data = get_json(url, params=params)
            if not data:
                continue
            for job in data.get("results", []):
                out.append(
                    RawJob(
                        source=self.name,
                        title=job.get("title", ""),
                        company=(job.get("company") or {}).get("display_name", ""),
                        location=(job.get("location") or {}).get("display_name", ""),
                        url=job.get("redirect_url", ""),
                        external_id=str(job.get("id", "")) or None,
                        description=job.get("description", ""),
                        salary_min=job.get("salary_min"),
                        salary_max=job.get("salary_max"),
                        salary_currency=currency,
                        posted_date=job.get("created"),
                        raw=job,
                    )
                )
        return out
