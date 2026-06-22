import re

import requests

from jobhorizon.logging_setup import get_logger

logger = get_logger(__name__)
DEFAULT_TIMEOUT = 15


def get_json(url: str, **kwargs):
    try:
        resp = requests.get(url, timeout=DEFAULT_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def post_json(url: str, **kwargs):
    try:
        resp = requests.post(url, timeout=DEFAULT_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("POST %s failed: %s", url, exc)
        return None


def title_matches(text: str, titles: list[str], skills: list[str]) -> bool:
    """Client-side relevance filter for full-feed sources (RemoteOK, Arbeitnow, Jobicy).
    Word-boundary matching -- plain substring matching false-positives on short skill
    names like "aws" or "r" appearing inside unrelated words in long descriptions."""
    t = (text or "").lower()
    for needle in (titles or []) + (skills or []):
        if needle and re.search(r"\b" + re.escape(needle.lower()) + r"\b", t):
            return True
    return False
