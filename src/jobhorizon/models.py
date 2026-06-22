from dataclasses import dataclass, field


@dataclass
class RawJob:
    """What an adapter returns. Adapters do not classify work_type or convert
    currency — that's normalize.py's job. `work_type_hint` is set only when the
    source itself gives a confident structured signal (e.g. a remote-only feed,
    or an explicit field like JobSpy's is_remote)."""

    source: str
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    external_id: str | None = None
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    posted_date: str | None = None
    work_type_hint: str | None = None  # remote | hybrid | onsite | None
    poster_name: str | None = None
    poster_email: str | None = None
    raw: dict = field(default_factory=dict)
