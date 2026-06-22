import json

import pytest

from jobhorizon import llm_client


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return _FakeResponse(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def _patch_client(monkeypatch, text):
    monkeypatch.setattr(llm_client, "_get_client", lambda: _FakeClient(text))


def test_extract_jd_requirements_parses_json_and_fills_missing_keys(monkeypatch):
    _patch_client(monkeypatch, json.dumps({"must_have": ["Python"]}))

    result = llm_client.extract_jd_requirements("some JD text", model="m")

    assert result["must_have"] == ["Python"]
    assert result["nice_to_have"] == []
    assert result["tools"] == []
    assert result["certs"] == []
    assert result["keywords"] == []


def test_extract_jd_requirements_extracts_json_from_surrounding_prose(monkeypatch):
    _patch_client(monkeypatch, 'Sure, here is the JSON: {"must_have": ["SQL"]} thanks!')

    result = llm_client.extract_jd_requirements("jd", model="m")

    assert result["must_have"] == ["SQL"]


def test_rephrase_bullets_empty_input_short_circuits():
    assert llm_client.rephrase_bullets([], {}, model="m") == []


def test_rephrase_bullets_returns_rewritten_list(monkeypatch):
    _patch_client(monkeypatch, json.dumps({"bullets": ["Rewrote bullet one"]}))

    result = llm_client.rephrase_bullets(["Original bullet one"], {"keywords": []}, model="m")

    assert result == ["Rewrote bullet one"]


def test_rephrase_bullets_falls_back_to_originals_on_count_mismatch(monkeypatch):
    _patch_client(monkeypatch, json.dumps({"bullets": ["only one"]}))
    originals = ["bullet one", "bullet two"]

    result = llm_client.rephrase_bullets(originals, {"keywords": []}, model="m")

    assert result == originals


def test_lint_bullets_llm_empty_input_short_circuits():
    assert llm_client.lint_bullets_llm([], [], model="m") == []


def test_lint_bullets_llm_returns_unsupported_list(monkeypatch):
    _patch_client(monkeypatch, json.dumps({"unsupported": ["bad bullet"]}))

    result = llm_client.lint_bullets_llm(["orig"], ["bad bullet"], model="m")

    assert result == ["bad bullet"]


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        llm_client._get_client()
