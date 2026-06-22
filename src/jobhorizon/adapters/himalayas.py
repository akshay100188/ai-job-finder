from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.adapters._util import get_json
from jobhorizon.criteria import Criteria
from jobhorizon.models import RawJob

# Attribution required by Himalayas' ToS: jobs sourced here must credit Himalayas
# and must not be resubmitted to other job boards.
ATTRIBUTION = "Source: Himalayas (himalayas.app)"


class HimalayasAdapter(JobSourceAdapter):
    name = "himalayas"
    requires_key = False

    def search(self, criteria: Criteria) -> list[RawJob]:
        out: list[RawJob] = []
        for title in criteria.titles or [""]:
            data = get_json("https://himalayas.app/jobs/api/search", params={"keywords": title, "limit": 25})
            if not data:
                continue
            jobs = data.get("jobs", data) if isinstance(data, dict) else data
            for job in jobs or []:
                location = job.get("locationRestrictions") or job.get("location")
                if isinstance(location, list):
                    location = ", ".join(location)
                out.append(
                    RawJob(
                        source=self.name,
                        title=job.get("title", ""),
                        company=job.get("companyName") or job.get("company", ""),
                        location=location or "",
                        url=job.get("applicationLink") or job.get("url", ""),
                        external_id=str(job.get("guid") or job.get("id") or "") or None,
                        description=f"{job.get('description', '')}\n\n{ATTRIBUTION}",
                        posted_date=job.get("pubDate") or job.get("publishedAt"),
                        work_type_hint="remote",
                        raw=job,
                    )
                )
        return out
