from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json, title_matches
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob


class JobicyAdapter(JobSourceAdapter):
    name = "jobicy"
    requires_key = False

    def search(self, criteria: Criteria) -> list[RawJob]:
        data = get_json("https://jobicy.com/api/v2/remote-jobs", params={"count": 50})
        if not data:
            return []
        out: list[RawJob] = []
        for job in data.get("jobs", []):
            text = f"{job.get('jobTitle', '')} {job.get('jobExcerpt', '')} {job.get('jobDescription', '')}"
            if not title_matches(text, criteria.titles, criteria.skills):
                continue
            out.append(
                RawJob(
                    source=self.name,
                    title=job.get("jobTitle", ""),
                    company=job.get("companyName", ""),
                    location=job.get("jobGeo", ""),
                    url=job.get("url", ""),
                    external_id=str(job.get("id", "")) or None,
                    description=job.get("jobDescription") or job.get("jobExcerpt", ""),
                    salary_min=job.get("annualSalaryMin"),
                    salary_max=job.get("annualSalaryMax"),
                    salary_currency=job.get("salaryCurrency"),
                    posted_date=job.get("pubDate"),
                    work_type_hint="remote",
                    raw=job,
                )
            )
        return out
