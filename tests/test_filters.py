from jobhorizon.filters import evaluate_gates


def _job_row(**overrides):
    row = {"work_type": "unknown", "location": "", "salary_max_inr": None}
    row.update(overrides)
    return row


def test_pay_gate_fails_below_minimum(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="hybrid", location="Noida", salary_max_inr=1000000)
    passed, reason = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is False
    assert reason == "pay_below_minimum"


def test_pay_gate_passes_when_salary_unknown(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="hybrid", location="Noida", salary_max_inr=None)
    passed, _ = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is True


def test_remote_mode_rejects_onsite(sample_criteria, filter_cfg, fx_rates):
    sample_criteria.working_mode = "remote"
    job = _job_row(work_type="onsite", salary_max_inr=2000000)
    passed, reason = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is False
    assert reason == "mode_not_remote"


def test_remote_mode_accepts_unknown_work_type(sample_criteria, filter_cfg, fx_rates):
    sample_criteria.working_mode = "remote"
    job = _job_row(work_type="unknown", salary_max_inr=2000000)
    passed, _ = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is True


def test_hybrid_mode_rejects_remote_work_type(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="remote", location="Noida", salary_max_inr=2000000)
    passed, reason = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is False
    assert reason == "mode_not_hybrid"


def test_hybrid_mode_location_reject_alias_fails(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="hybrid", location="Gurgaon, India", salary_max_inr=2000000)
    passed, reason = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is False
    assert reason == "location_rejected"


def test_hybrid_mode_location_accept_alias_passes(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="hybrid", location="Noida, India", salary_max_inr=2000000)
    passed, _ = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is True


def test_hybrid_mode_ambiguous_location_passes_recall_bias(sample_criteria, filter_cfg, fx_rates):
    job = _job_row(work_type="hybrid", location="Somewhere Else", salary_max_inr=2000000)
    passed, _ = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is True


def test_any_mode_ignores_work_type_and_location(sample_criteria, filter_cfg, fx_rates):
    sample_criteria.working_mode = "any"
    job = _job_row(work_type="onsite", location="Gurgaon", salary_max_inr=2000000)
    passed, _ = evaluate_gates(job, sample_criteria, filter_cfg, fx_rates)
    assert passed is True
