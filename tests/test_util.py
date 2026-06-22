from jobhorizon.adapters._util import title_matches


def test_title_matches_on_skill_word():
    assert title_matches("Looking for a Python developer", [], ["python"]) is True


def test_title_matches_false_positive_substring_is_rejected():
    text = "We help customers who file insurance claims and review legal flaws in policies"
    assert title_matches(text, [], ["aws"]) is False


def test_title_matches_no_match_returns_false():
    assert title_matches("Graphic Designer role", ["Backend Engineer"], ["python"]) is False
