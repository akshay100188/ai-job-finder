import feedparser

from jobhorizon.adapters import JobSourceAdapter
from jobhorizon.criteria import Criteria
from jobhorizon.logging_setup import get_logger
from jobhorizon.models import RawJob

logger = get_logger(__name__)


class WWRAdapter(JobSourceAdapter):
    name = "wwr"
    requires_key = False

    def __init__(self, categories: list[str] | None = None):
        self.categories = categories or ["remote-jobs"]

    def search(self, criteria: Criteria) -> list[RawJob]:
        out: list[RawJob] = []
        for category in self.categories:
            url = f"https://weworkremotely.com/categories/{category}/jobs.rss"
            try:
                feed = feedparser.parse(url)
            except Exception as exc:
                logger.warning("WWR feed %s failed: %s", url, exc)
                continue
            for entry in feed.entries:
                # WWR RSS titles are formatted "Company Name: Job Title"
                title = entry.get("title", "")
                company, _, job_title = title.partition(": ")
                if not job_title:
                    job_title, company = company, ""
                out.append(
                    RawJob(
                        source=self.name,
                        title=job_title or title,
                        company=company,
                        location="",
                        url=entry.get("link", ""),
                        external_id=entry.get("id"),
                        description=entry.get("summary", ""),
                        posted_date=entry.get("published"),
                        work_type_hint="remote",
                        raw={"title": title, "link": entry.get("link"), "published": entry.get("published")},
                    )
                )
        return out
