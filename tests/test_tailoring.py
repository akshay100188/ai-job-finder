from pathlib import Path

import pytest

from jobhorizon import db, llm_client, tailoring
from jobhorizon.config import AppConfig, Secrets, TailoringConfig
from jobhorizon.master_resume import (
    Certification,
    Contact,
    ExperienceEntry,
    MasterResume,
    Project,
    build_fact_set,
)


def _sample_master() -> MasterResume:
    return MasterResume(
        contact=Contact(name="Jane Doe", email="jane@example.com"),
        summary="Backend engineer.",
        experience=[
            ExperienceEntry(
                company="Acme",
                role="Backend Engineer",
                start="2020-01",
                end="present",
                bullets=[
                    "Rebuilt the risk pipeline in Python, cutting latency from 40 to 9 minutes.",
                    "Managed a team of 3 engineers.",
                ],
                skills=["Python", "AWS"],
            )
        ],
        skills=["Python", "AWS", "SQL"],
        certifications=[Certification(name="AWS Certified Solutions Architect")],
        projects=[
            Project(name="Backtester", bullets=["Built a backtester in pandas."], skills=["pandas"]),
        ],
    )


def _seed_job(conn, job_id="j1", description="We need Python and Kubernetes experience.", status="relevant"):
    job = {
        "job_id": job_id,
        "source": "remoteok",
        "external_id": "1",
        "url": "http://x",
        "title": "Backend Engineer",
        "company": "Acme",
        "location": "Noida",
        "work_type": "hybrid",
        "description": description,
        "salary_min": None,
        "salary_max": None,
        "salary_currency": None,
        "salary_min_inr": None,
        "salary_max_inr": None,
        "poster_name": None,
        "poster_email": None,
        "posted_date": None,
        "raw_json": "{}",
    }
    db.upsert_job(conn, job)
    db.replace_job_score(
        conn,
        {
            "job_id": job_id,
            "gate_passed": True,
            "gate_reason": "passed",
            "skills_matched": 1,
            "skills_matched_list": "[]",
            "score": 0.8,
            "model_source": "deterministic",
        },
    )
    db.ensure_review_row(conn, job_id)
    if status != "new":
        db.update_review_status(conn, job_id, status, False)
    conn.commit()
    return job_id


def _app_config(filter_cfg, scoring_cfg, fx_rates, **tailoring_overrides) -> AppConfig:
    return AppConfig(
        sources={},
        filter=filter_cfg,
        scoring=scoring_cfg,
        fx_rates_to_inr=fx_rates,
        secrets=Secrets(),
        tailoring=TailoringConfig(**tailoring_overrides),
    )


def test_match_requirements_categorizes_satisfied_partial_and_gap():
    master = _sample_master()
    jd = {"must_have": ["Python", "Kubernetes"], "nice_to_have": ["risk pipeline"]}

    result = tailoring.match_requirements(jd, master)

    assert result["must_have"]["Python"] == "satisfied"
    assert result["must_have"]["Kubernetes"] == "gap"
    assert result["nice_to_have"]["risk pipeline"] == "partial"


def test_select_and_reorder_prioritizes_relevant_bullets():
    master = _sample_master()
    jd = {"keywords": ["python", "risk"]}

    selected = tailoring.select_and_reorder(jd, master)

    assert selected[0].relevance >= selected[-1].relevance
    assert any("risk pipeline" in b.text.lower() for b in selected if b.relevance > 0)


def test_select_and_reorder_falls_back_when_nothing_matches():
    master = _sample_master()
    jd = {"keywords": ["unrelated_keyword_xyz"]}

    selected = tailoring.select_and_reorder(jd, master)

    assert len(selected) > 0
    assert all(b.relevance == 0 for b in selected)


def test_fabrication_lint_flags_invented_skill_term():
    fact_set = build_fact_set(_sample_master())
    originals = ["Worked on backend systems."]
    rephrased = ["Worked on backend systems using Kubernetes."]

    flags = tailoring.fabrication_lint(originals, rephrased, fact_set, jd_vocab={"kubernetes"})

    assert any("kubernetes" in f.lower() for f in flags)


def test_fabrication_lint_flags_invented_number():
    fact_set = build_fact_set(_sample_master())
    originals = ["Cut latency."]
    rephrased = ["Cut latency by 90%."]

    flags = tailoring.fabrication_lint(originals, rephrased, fact_set, jd_vocab=set())

    assert any("90%" in f for f in flags)


def test_fabrication_lint_passes_clean_rephrase():
    fact_set = build_fact_set(_sample_master())
    originals = ["Rebuilt the risk pipeline in Python, cutting latency from 40 to 9 minutes."]
    rephrased = ["Re-engineered the risk pipeline in Python, reducing latency from 40 to 9 minutes."]

    flags = tailoring.fabrication_lint(originals, rephrased, fact_set, jd_vocab={"python"})

    assert flags == []


def test_build_gap_report_lists_gaps_and_handles_no_gaps():
    report = tailoring.build_gap_report({"must_have": {"Kubernetes": "gap"}, "nice_to_have": {}})
    assert "Kubernetes" in report

    clean_report = tailoring.build_gap_report({"must_have": {"Python": "satisfied"}, "nice_to_have": {}})
    assert "No gaps found" in clean_report


def test_tailor_job_requires_relevant_status(conn, filter_cfg, scoring_cfg, fx_rates):
    job_id = _seed_job(conn, status="new")
    app_config = _app_config(filter_cfg, scoring_cfg, fx_rates)

    with pytest.raises(ValueError):
        tailoring.tailor_job(conn, job_id, app_config)


def test_tailor_job_unknown_job_raises(conn, filter_cfg, scoring_cfg, fx_rates):
    app_config = _app_config(filter_cfg, scoring_cfg, fx_rates)

    with pytest.raises(ValueError):
        tailoring.tailor_job(conn, "nope", app_config)


def test_tailor_job_full_pipeline_clean(conn, filter_cfg, scoring_cfg, fx_rates, tmp_path, monkeypatch):
    master_path = tmp_path / "master_resume.yaml"
    master_path.write_text(
        """
contact:
  name: Jane Doe
  email: jane@example.com
experience:
  - company: Acme
    role: Backend Engineer
    start: "2020-01"
    end: present
    bullets:
      - "Rebuilt the risk pipeline in Python, cutting latency from 40 to 9 minutes."
    skills: ["Python"]
skills: ["Python", "SQL"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tailoring, "MASTER_RESUME_PATH", master_path)
    monkeypatch.setattr(tailoring, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        llm_client,
        "extract_jd_requirements",
        lambda jd_text, model: {
            "must_have": ["Python"],
            "nice_to_have": [],
            "tools": [],
            "certs": [],
            "keywords": ["python"],
        },
    )
    monkeypatch.setattr(
        llm_client, "rephrase_bullets", lambda bullets, jd, model: [f"Rephrased: {b}" for b in bullets]
    )
    monkeypatch.setattr(llm_client, "lint_bullets_llm", lambda originals, rephrased, model: [])

    job_id = _seed_job(conn)
    app_config = _app_config(filter_cfg, scoring_cfg, fx_rates, run_lint_llm_pass=True)

    report = tailoring.tailor_job(conn, job_id, app_config)

    assert report["lint_status"] == "clean"
    assert report["lint_flags"] == []
    assert Path(report["docx_path"]).exists()
    assert Path(report["md_path"]).exists()
    assert Path(report["gap_report_path"]).exists()

    rows = db.fetch_tailored_resumes(conn, job_id)
    assert len(rows) == 1
    assert rows[0]["lint_status"] == "clean"


def test_tailor_job_lint_flags_invented_content_falls_back_to_original_wording(
    conn, filter_cfg, scoring_cfg, fx_rates, tmp_path, monkeypatch
):
    master_path = tmp_path / "master_resume.yaml"
    master_path.write_text(
        """
contact:
  name: Jane Doe
experience:
  - company: Acme
    role: Backend Engineer
    bullets:
      - "Improved system performance."
skills: ["Python"]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(tailoring, "MASTER_RESUME_PATH", master_path)
    monkeypatch.setattr(tailoring, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        llm_client,
        "extract_jd_requirements",
        lambda jd_text, model: {
            "must_have": [],
            "nice_to_have": [],
            "tools": [],
            "certs": [],
            "keywords": [],
        },
    )
    monkeypatch.setattr(
        llm_client, "rephrase_bullets", lambda bullets, jd, model: ["Improved system performance by 90%."]
    )

    job_id = _seed_job(conn)
    app_config = _app_config(filter_cfg, scoring_cfg, fx_rates, run_lint_llm_pass=False)

    report = tailoring.tailor_job(conn, job_id, app_config)

    assert report["lint_status"] == "flagged"
    assert any("90%" in f for f in report["lint_flags"])
    md_text = Path(report["md_path"]).read_text(encoding="utf-8")
    assert "Improved system performance." in md_text
    assert "90%" not in md_text


def test_tailor_job_respects_output_formats_config(
    conn, filter_cfg, scoring_cfg, fx_rates, tmp_path, monkeypatch
):
    master_path = tmp_path / "master_resume.yaml"
    master_path.write_text("contact:\n  name: Jane\nexperience: []\nskills: []\n", encoding="utf-8")
    monkeypatch.setattr(tailoring, "MASTER_RESUME_PATH", master_path)
    monkeypatch.setattr(tailoring, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(
        llm_client,
        "extract_jd_requirements",
        lambda jd_text, model: {
            "must_have": [],
            "nice_to_have": [],
            "tools": [],
            "certs": [],
            "keywords": [],
        },
    )
    monkeypatch.setattr(llm_client, "rephrase_bullets", lambda bullets, jd, model: bullets)

    job_id = _seed_job(conn)
    app_config = _app_config(
        filter_cfg, scoring_cfg, fx_rates, output_formats=["md"], run_lint_llm_pass=False
    )

    report = tailoring.tailor_job(conn, job_id, app_config)

    assert report["docx_path"] is None
    assert report["md_path"] is not None
