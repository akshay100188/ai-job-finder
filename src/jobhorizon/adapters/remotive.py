from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob


class RemotiveAdapter(JobSourceAdapter):
    name = "remotive"
    requires_key = False

    def search(self, criteria: Criteria) -> list[RawJob]:
        out: list[RawJob] = []
        for title in criteria.titles or [""]:
            data = get_json("https://remotive.com/api/remote-jobs", params={"search": title})
            if not data:
                continue
            for job in data.get("jobs", []):
                out.append(
                    RawJob(
                        source=self.name,
                        title=job.get("title", ""),
                        company=job.get("company_name", ""),
                        location=job.get("candidate_required_location", ""),
                        url=job.get("url", ""),
                        external_id=str(job.get("id", "")) or None,
                        description=job.get("description", ""),
                        # Remotive's "salary" field is unstructured free text (e.g. "$60,000 - 90,000"),
                        # not reliably parseable -- left null, recall bias on the pay gate.
                        posted_date=job.get("publication_date"),
                        work_type_hint="remote",
                        raw=job,
                    )
                )
        return out
