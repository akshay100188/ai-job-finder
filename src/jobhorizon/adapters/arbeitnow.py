from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json, title_matches
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob


class ArbeitnowAdapter(JobSourceAdapter):
    name = "arbeitnow"
    requires_key = False

    def search(self, criteria: Criteria) -> list[RawJob]:
        data = get_json("https://www.arbeitnow.com/api/job-board-api")
        if not data:
            return []
        out: list[RawJob] = []
        for job in data.get("data", []):
            text = f"{job.get('title', '')} {' '.join(job.get('tags', []))} {job.get('description', '')}"
            if not title_matches(text, criteria.titles, criteria.skills):
                continue
            out.append(
                RawJob(
                    source=self.name,
                    title=job.get("title", ""),
                    company=job.get("company_name", ""),
                    location=job.get("location", ""),
                    url=job.get("url", ""),
                    external_id=job.get("slug"),
                    description=job.get("description", ""),
                    posted_date=job.get("created_at"),
                    work_type_hint="remote" if job.get("remote") else None,
                    raw=job,
                )
            )
        return out
