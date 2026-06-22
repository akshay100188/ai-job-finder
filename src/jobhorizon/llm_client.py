import json
import os

import anthropic

from jobhorizon.logging_setup import get_logger

logger = get_logger(__name__)

_EXTRACT_SYSTEM_PROMPT = (
    "You are a precise job-description parser. Given a job description, extract structured "
    "requirements as JSON only, with no prose before or after. Schema: "
    '{"must_have": [string], "nice_to_have": [string], "tools": [string], '
    '"certs": [string], "keywords": [string]}. Use short noun phrases taken from the text. '
    "Do not invent requirements that are not present in the text."
)

_REPHRASE_SYSTEM_PROMPT = (
    "You rewrite resume bullets to use a target job's vocabulary, WITHOUT changing any facts. "
    "Hard rules: do not invent skills, tools, numbers, employers, roles, or dates that are not "
    "already present in the bullet you are rewriting. Only rephrase wording or emphasis using the "
    "supplied JD keywords where they genuinely describe the same work. Return JSON only: "
    '{"bullets": [string, ...]} with the same order and count as the input bullets.'
)

_LINT_SYSTEM_PROMPT = (
    "You are a fact-checker for resume bullets. For each rewritten bullet, decide whether it is "
    "fully supported by its corresponding original bullet (same facts, possibly different wording). "
    'Return JSON only: {"unsupported": [string, ...]} listing the rewritten bullets, verbatim, that '
    "introduce any claim, skill, tool, or number not present in their original."
)


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Phase 3 resume tailoring needs your own Anthropic key "
            "in .env -- the daily pipeline never needs it."
        )
    return anthropic.Anthropic(api_key=api_key)


def _call_json(system: str, user: str, model: str, max_tokens: int = 2000) -> dict:
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            logger.warning("LLM response had no JSON object: %r", text[:200])
            raise
        return json.loads(text[start : end + 1])


def extract_jd_requirements(jd_text: str, model: str) -> dict:
    result = _call_json(_EXTRACT_SYSTEM_PROMPT, jd_text, model)
    for key in ("must_have", "nice_to_have", "tools", "certs", "keywords"):
        result.setdefault(key, [])
    return result


def rephrase_bullets(bullets: list[str], jd_requirements: dict, model: str) -> list[str]:
    if not bullets:
        return []
    user = json.dumps({"bullets": bullets, "jd_keywords": jd_requirements.get("keywords", [])})
    result = _call_json(_REPHRASE_SYSTEM_PROMPT, user, model)
    rephrased = result.get("bullets", [])
    if len(rephrased) != len(bullets):
        logger.warning(
            "rephrase bullet count mismatch (%d in, %d out) - keeping originals",
            len(bullets),
            len(rephrased),
        )
        return bullets
    return rephrased


def lint_bullets_llm(originals: list[str], rephrased: list[str], model: str) -> list[str]:
    if not rephrased:
        return []
    pairs = [{"original": o, "rephrased": r} for o, r in zip(originals, rephrased, strict=True)]
    result = _call_json(_LINT_SYSTEM_PROMPT, json.dumps({"pairs": pairs}), model)
    return result.get("unsupported", [])
