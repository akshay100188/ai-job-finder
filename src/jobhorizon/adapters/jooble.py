from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import post_json
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob


class JoobleAdapter(JobSourceAdapter):
    name = "jooble"
    requires_key = True

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, criteria: Criteria) -> list[RawJob]:
        url = f"https://jooble.org/api/{self.api_key}"
        out: list[RawJob] = []
        for title in criteria.titles or [""]:
            body = {"keywords": title, "location": criteria.location or ""}
            data = post_json(url, json=body)
            if not data:
                continue
            for job in data.get("jobs", []):
                out.append(
                    RawJob(
                        source=self.name,
                        title=job.get("title", ""),
                        company=job.get("company", ""),
                        location=job.get("location", ""),
                        url=job.get("link", ""),
                        external_id=job.get("id"),
                        description=job.get("snippet", ""),
                        # Jooble's "salary" field is unstructured free text (e.g. "$80k-100k"),
                        # not reliably parseable -- left null, recall bias on the pay gate.
                        posted_date=job.get("updated"),
                        raw=job,
                    )
                )
        return out
