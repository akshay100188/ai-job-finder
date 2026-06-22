import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_NUMBER_RE = re.compile(r"[$₹]?\d[\d,]*\.?\d*%?")


@dataclass
class Contact:
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    website: str = ""


@dataclass
class ExperienceEntry:
    company: str
    role: str
    start: str = ""
    end: str = ""
    location: str = ""
    bullets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class Certification:
    name: str
    issuer: str = ""
    date: str = ""


@dataclass
class Education:
    degree: str
    institution: str
    year: str = ""


@dataclass
class Project:
    name: str
    description: str = ""
    bullets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class MasterResume:
    contact: Contact
    summary: str = ""
    experience: list[ExperienceEntry] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)


@dataclass
class FactSet:
    """Ground truth extracted from the master resume -- what the fabrication lint
    checks tailored output against. Every claim in a tailored resume must trace
    back to one of these sets."""

    skills: set[str]
    numbers: set[str]
    employers: set[str]
    roles: set[str]
    dates: set[str]
    certifications: set[str]


def load_master_resume(path: Path) -> MasterResume:
    if not path.exists():
        raise FileNotFoundError(
            f"Master resume not found at {path}. Copy data/master_resume.example.yaml to "
            "data/master_resume.yaml and fill in your real history before tailoring."
        )
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    experience = [
        ExperienceEntry(
            company=e["company"],
            role=e["role"],
            start=e.get("start", ""),
            end=e.get("end", ""),
            location=e.get("location", ""),
            bullets=e.get("bullets", []) or [],
            skills=e.get("skills", []) or [],
        )
        for e in raw.get("experience", []) or []
    ]
    certifications = [
        Certification(name=c["name"], issuer=c.get("issuer", ""), date=c.get("date", ""))
        for c in raw.get("certifications", []) or []
    ]
    education = [
        Education(degree=e["degree"], institution=e["institution"], year=e.get("year", ""))
        for e in raw.get("education", []) or []
    ]
    projects = [
        Project(
            name=p["name"],
            description=p.get("description", ""),
            bullets=p.get("bullets", []) or [],
            skills=p.get("skills", []) or [],
        )
        for p in raw.get("projects", []) or []
    ]

    return MasterResume(
        contact=Contact(**(raw.get("contact", {}) or {})),
        summary=raw.get("summary", ""),
        experience=experience,
        skills=raw.get("skills", []) or [],
        certifications=certifications,
        education=education,
        projects=projects,
    )


def _extract_numbers(text: str) -> set[str]:
    return {m.group(0) for m in _NUMBER_RE.finditer(text)}


def build_fact_set(master: MasterResume) -> FactSet:
    skills = {s.lower() for s in master.skills}
    for exp in master.experience:
        skills.update(s.lower() for s in exp.skills)
    for proj in master.projects:
        skills.update(s.lower() for s in proj.skills)

    numbers: set[str] = set()
    employers: set[str] = set()
    roles: set[str] = set()
    dates: set[str] = set()
    for exp in master.experience:
        employers.add(exp.company.lower())
        roles.add(exp.role.lower())
        dates.add(exp.start)
        dates.add(exp.end)
        for bullet in exp.bullets:
            numbers.update(_extract_numbers(bullet))
    for proj in master.projects:
        for bullet in proj.bullets:
            numbers.update(_extract_numbers(bullet))

    certifications = {c.name.lower() for c in master.certifications}

    return FactSet(
        skills=skills,
        numbers=numbers,
        employers=employers,
        roles=roles,
        dates=dates,
        certifications=certifications,
    )
