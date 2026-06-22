from jobhorizon.scoring import score_job


def test_full_skill_match_scores_one(sample_criteria, scoring_cfg):
    job = {"title": "Python SQL AWS Engineer", "description": ""}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert result["skills_matched"] == 3
    assert result["score"] == 1.0


def test_no_skill_match_scores_zero(sample_criteria, scoring_cfg):
    job = {"title": "Java Developer", "description": "Spring Boot"}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert result["skills_matched"] == 0
    assert result["score"] == 0.0


def test_partial_skill_match_is_proportional(sample_criteria, scoring_cfg):
    job = {"title": "Python Engineer", "description": ""}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert result["skills_matched"] == 1
    assert round(result["score"], 4) == round(1 / 3, 4)


def test_domain_boost_added_on_keyword_hit(sample_criteria, scoring_cfg):
    job = {"title": "Python Engineer", "description": "exposure to capital markets"}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert round(result["score"], 4) == round(1 / 3 + 0.1, 4)


def test_score_clamped_at_one(sample_criteria, scoring_cfg):
    scoring_cfg.domain_boost = 1.0
    job = {"title": "Python SQL AWS Engineer", "description": "fixed income desk"}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert result["score"] == 1.0


def test_word_boundary_prevents_substring_match(sample_criteria, scoring_cfg):
    sample_criteria.skills = ["R"]
    job = {"title": "Senior Recruiter", "description": ""}
    result = score_job(job, sample_criteria, scoring_cfg)
    assert result["skills_matched"] == 0
