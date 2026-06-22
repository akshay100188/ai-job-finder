import re

from jobhorizon.adapters.adzuna import AdzunaAdapter
from jobhorizon.adapters.remoteok import RemoteOKAdapter
from jobhorizon.adapters.wwr import WWRAdapter


def test_adzuna_search_maps_fields(requests_mock, sample_criteria):
    sample_criteria.titles = ["Backend Engineer"]
    requests_mock.get(
        re.compile(r"https://api\.adzuna\.com/.*"),
        json={
            "results": [
                {
                    "title": "Backend Engineer",
                    "company": {"display_name": "Acme"},
                    "location": {"display_name": "Bangalore"},
                    "redirect_url": "http://example.com/job/123",
                    "id": 123,
                    "description": "Python role",
                    "salary_min": 1000000,
                    "salary_max": 2000000,
                    "created": "2026-06-01T00:00:00Z",
                }
            ]
        },
    )
    adapter = AdzunaAdapter(app_id="id", app_key="key", country="in")
    jobs = adapter.search(sample_criteria)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.title == "Backend Engineer"
    assert job.company == "Acme"
    assert job.location == "Bangalore"
    assert job.salary_currency == "INR"
    assert job.external_id == "123"


def test_adzuna_skips_silently_on_request_failure(requests_mock, sample_criteria):
    sample_criteria.titles = ["Backend Engineer"]
    requests_mock.get(re.compile(r"https://api\.adzuna\.com/.*"), status_code=500)
    adapter = AdzunaAdapter(app_id="id", app_key="key", country="in")
    assert adapter.search(sample_criteria) == []


def test_remoteok_skips_meta_entry_and_filters_by_title(requests_mock, sample_criteria):
    sample_criteria.titles = ["Backend Engineer"]
    requests_mock.get(
        "https://remoteok.com/api",
        json=[
            {"legal": "this is the meta/legal notice, has no 'position' field"},
            {
                "id": "1",
                "position": "Backend Engineer",
                "company": "Acme",
                "tags": ["python"],
                "url": "http://x",
                "description": "",
                "date": "2026-06-01",
            },
            {
                "id": "2",
                "position": "Graphic Designer",
                "company": "Beta",
                "tags": [],
                "url": "http://y",
                "description": "",
            },
        ],
    )
    jobs = RemoteOKAdapter().search(sample_criteria)

    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].work_type_hint == "remote"


def test_wwr_splits_company_and_title_from_rss_title(monkeypatch, sample_criteria):
    class FakeFeed:
        entries = [
            {
                "title": "Acme Corp: Backend Engineer",
                "link": "http://example.com/job",
                "summary": "Great backend role",
                "published": "2026-06-01",
                "id": "guid-1",
            }
        ]

    monkeypatch.setattr("jobhorizon.adapters.wwr.feedparser.parse", lambda url: FakeFeed())
    jobs = WWRAdapter(categories=["remote-jobs"]).search(sample_criteria)

    assert len(jobs) == 1
    assert jobs[0].company == "Acme Corp"
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].work_type_hint == "remote"
