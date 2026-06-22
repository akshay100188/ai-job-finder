import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from jobhorizon import db, llm_client
from jobhorizon.config import AppConfig
from jobhorizon.docx_render import render_docx, render_resume_md
from jobhorizon.master_resume import FactSet, MasterResume, build_fact_set, load_master_resume
from jobhorizon.paths import MASTER_RESUME_PATH, OUTPUTS_DIR

_NUMBER_RE = re.compile(r"[$₹]?\d[\d,]*\.?\d*%?")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Selection ceiling so a long career history doesn't produce an unreadable resume --
# a senior-resume convention, not a hard spec requirement.
MAX_SELECTED_BULLETS = 12


def _slug(text: str) -> str:
    return _SLUG_RE.sub("_", text.lower()).strip("_") or "x"


@dataclass
class ScoredBullet:
    source: str  # "experience:<company>" or "project:<name>"
    text: str
    relevance: int


def _requirement_vocab(jd: dict) -> set[str]:
    vocab: set[str] = set()
    for key in ("must_have", "nice_to_have", "tools", "certs", "keywords"):
        vocab.update(v.lower() for v in jd.get(key, []))
    return vocab


def match_requirements(jd: dict, master: MasterResume) -> dict:
    fact_set = build_fact_set(master)
    bullet_text = " ".join(bullet.lower() for exp in master.experience for bullet in exp.bullets)
    bullet_text += " " + " ".join(bullet.lower() for proj in master.projects for bullet in proj.bullets)

    def _status(requirement: str) -> str:
        req = requirement.lower()
        if req in fact_set.skills or req in fact_set.certifications:
            return "satisfied"
        if re.search(r"\b" + re.escape(req) + r"\b", bullet_text):
            return "partial"
        return "gap"

    return {
        "must_have": {req: _status(req) for req in jd.get("must_have", [])},
        "nice_to_have": {req: _status(req) for req in jd.get("nice_to_have", [])},
    }


def select_and_reorder(jd: dict, master: MasterResume) -> list[ScoredBullet]:
    vocab = _requirement_vocab(jd)

    def _score(text: str) -> int:
        t = text.lower()
        return sum(1 for kw in vocab if re.search(r"\b" + re.escape(kw) + r"\b", t))

    scored = []
    for exp in master.experience:
        for bullet in exp.bullets:
            scored.append(ScoredBullet(f"experience:{exp.company}", bullet, _score(bullet)))
    for proj in master.projects:
        for bullet in proj.bullets:
            scored.append(ScoredBullet(f"project:{proj.name}", bullet, _score(bullet)))

    scored.sort(key=lambda b: b.relevance, reverse=True)
    relevant = [b for b in scored if b.relevance > 0]
    selected = relevant if relevant else scored[:MAX_SELECTED_BULLETS]
    return selected[:MAX_SELECTED_BULLETS]


def fabrication_lint(
    originals: list[str], rephrased: list[str], fact_set: FactSet, jd_vocab: set[str]
) -> list[str]:
    """The fabrication-lint hard floor (brief section 6). Flags anything the LLM's
    rephrase introduced that isn't traceable to the master resume: JD vocabulary
    echoed into a bullet without backing, or a number that wasn't in the original."""
    flags = []
    for original, candidate in zip(originals, rephrased, strict=True):
        orig_lower = original.lower()
        cand_lower = candidate.lower()

        for kw in jd_vocab:
            if kw in cand_lower and kw not in orig_lower and kw not in fact_set.skills:
                flags.append(f"introduced unverified term '{kw}' in: {candidate}")

        cand_numbers = {m.group(0) for m in _NUMBER_RE.finditer(candidate)}
        orig_numbers = {m.group(0) for m in _NUMBER_RE.finditer(original)}
        for number in cand_numbers - orig_numbers - fact_set.numbers:
            flags.append(f"invented number '{number}' in: {candidate}")

    return flags


def build_gap_report(match_result: dict) -> str:
    lines = ["# Gap report", ""]
    any_gaps = False
    for category, label in (("must_have", "Must-have"), ("nice_to_have", "Nice-to-have")):
        gaps = [req for req, status in match_result[category].items() if status == "gap"]
        if not gaps:
            continue
        any_gaps = True
        lines.append(f"## {label} requirements not covered by your master resume")
        lines.append("")
        for req in gaps:
            lines.append(
                f"- **{req}** - not found in your master resume. Consider whether related "
                "experience exists that the resume doesn't capture yet, or treat this as a "
                "genuine gap for this role."
            )
        lines.append("")
    if not any_gaps:
        lines.append("No gaps found against your master resume's stated skills/experience.")
    return "\n".join(lines)


def _bullets_by_source(
    selected: list[ScoredBullet], final_texts: list[str]
) -> dict[str, list[tuple[str, str]]]:
    mapping: dict[str, list[tuple[str, str]]] = {}
    for bullet, final in zip(selected, final_texts, strict=True):
        mapping.setdefault(bullet.source, []).append((bullet.text, final))
    return mapping


def tailor_job(conn: sqlite3.Connection, job_id: str, app_config: AppConfig) -> dict:
    job_row = db.get_job_with_score(conn, job_id)
    if job_row is None:
        raise ValueError(f"unknown job_id: {job_id}")
    if db.get_review_status(conn, job_id) != "relevant":
        raise ValueError("job must be marked relevant before tailoring")

    master = load_master_resume(MASTER_RESUME_PATH)
    fact_set = build_fact_set(master)

    jd = llm_client.extract_jd_requirements(
        job_row.get("description") or "", app_config.tailoring.model_extract
    )
    jd_vocab = _requirement_vocab(jd)

    match_result = match_requirements(jd, master)
    selected = select_and_reorder(jd, master)
    originals = [b.text for b in selected]

    rephrased = llm_client.rephrase_bullets(originals, jd, app_config.tailoring.model_rephrase)

    flags = fabrication_lint(originals, rephrased, fact_set, jd_vocab)
    if not flags and app_config.tailoring.run_lint_llm_pass:
        flags = llm_client.lint_bullets_llm(originals, rephrased, app_config.tailoring.model_rephrase)

    lint_status = "flagged" if flags else "clean"
    # Whole-batch fallback rather than per-bullet exclusion: if anything is flagged,
    # ship the unmodified master wording (100% traceable) instead of trying to
    # surgically patch just the offending phrase out of an LLM rewrite.
    final_texts = originals if flags else rephrased
    bullets_by_source = _bullets_by_source(selected, final_texts)

    company_slug = _slug(job_row.get("company") or "company")
    title_slug = _slug(job_row.get("title") or "role")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    base_name = f"{company_slug}_{title_slug}_{ts}"

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    docx_path = OUTPUTS_DIR / f"{base_name}.docx" if "docx" in app_config.tailoring.output_formats else None
    md_path = OUTPUTS_DIR / f"{base_name}.md" if "md" in app_config.tailoring.output_formats else None
    gap_path = OUTPUTS_DIR / f"{base_name}_gaps.md"

    include_summary = app_config.tailoring.include_tailored_summary
    if docx_path is not None:
        render_docx(master, bullets_by_source, docx_path, include_summary=include_summary)
    if md_path is not None:
        render_resume_md(master, bullets_by_source, md_path, include_summary=include_summary)
    gap_path.write_text(build_gap_report(match_result), encoding="utf-8")

    record_id = db.insert_tailored_resume(
        conn,
        {
            "job_id": job_id,
            "docx_path": str(docx_path) if docx_path else None,
            "md_path": str(md_path) if md_path else None,
            "gap_report_path": str(gap_path),
            "lint_status": lint_status,
            "lint_flags": json.dumps(flags),
        },
    )

    return {
        "id": record_id,
        "lint_status": lint_status,
        "lint_flags": flags,
        "docx_path": str(docx_path) if docx_path else None,
        "md_path": str(md_path) if md_path else None,
        "gap_report_path": str(gap_path),
    }
