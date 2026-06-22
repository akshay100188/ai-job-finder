import pytest

from jobhorizon.master_resume import (
    Certification,
    Contact,
    ExperienceEntry,
    MasterResume,
    Project,
    build_fact_set,
    load_master_resume,
)
from jobhorizon.paths import REPO_ROOT


def test_load_master_resume_example_file():
    master = load_master_resume(REPO_ROOT / "data" / "master_resume.example.yaml")
    assert master.contact.name == "Jane Doe"
    assert master.experience[0].company == "Example Capital Markets Pvt Ltd"
    assert "Python" in master.skills


def test_load_master_resume_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_master_resume(tmp_path / "nope.yaml")


def _sample_master() -> MasterResume:
    return MasterResume(
        contact=Contact(name="Jane Doe"),
        experience=[
            ExperienceEntry(
                company="Acme",
                role="Engineer",
                start="2020-01",
                end="present",
                bullets=["Cut latency by 40%", "Led a team of 3 engineers"],
                skills=["Python"],
            )
        ],
        skills=["Python", "SQL"],
        certifications=[Certification(name="AWS Certified Solutions Architect")],
        projects=[
            Project(name="Side project", bullets=["Built a tool that saved $500"], skills=["pandas"]),
        ],
    )


def test_build_fact_set_collects_skills_numbers_employers_roles_certs():
    fact_set = build_fact_set(_sample_master())

    assert "python" in fact_set.skills
    assert "pandas" in fact_set.skills
    assert "acme" in fact_set.employers
    assert "engineer" in fact_set.roles
    assert "aws certified solutions architect" in fact_set.certifications
    assert "40%" in fact_set.numbers
    assert "3" in fact_set.numbers
    assert "$500" in fact_set.numbers
