from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json, title_matches
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob


class RemoteOKAdapter(JobSourceAdapter):
    name = "remoteok"
    requires_key = False

    def search(self, criteria: Criteria) -> list[RawJob]:
        data = get_json("https://remoteok.com/api")
        if not data:
            return []
        out: list[RawJob] = []
        for job in data:
            if "position" not in job:
                continue  # first element is a legal/meta notice, not a job
            text = f"{job.get('position', '')} {' '.join(job.get('tags', []))} {job.get('description', '')}"
            if not title_matches(text, criteria.titles, criteria.skills):
                continue
            out.append(
                RawJob(
                    source=self.name,
                    title=job.get("position", ""),
                    company=job.get("company", ""),
                    location=job.get("location", ""),
                    url=job.get("url", ""),
                    external_id=str(job.get("id", "")) or None,
                    description=job.get("description", ""),
                    salary_min=job.get("salary_min"),
                    salary_max=job.get("salary_max"),
                    salary_currency="USD" if job.get("salary_min") else None,
                    posted_date=job.get("date"),
                    work_type_hint="remote",
                    raw=job,
                )
            )
        return out
