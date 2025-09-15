"""Tests for the Hirex matching engine."""

from __future__ import annotations

from hirex.engine import MatchingEngine
from hirex.models import CandidateProfile, JobPosting, MatchingWeights


def _sample_candidate(**overrides):
    data = dict(
        id="cand-1",
        full_name="Alex Dev",
        years_experience=5,
        skills=["Python", "FastAPI", "SQL"],
        desired_salary=90000,
        preferred_locations=["berlin"],
        open_to_remote=True,
        industries=["SaaS", "FinTech"],
    )
    data.update(overrides)
    return CandidateProfile(**data)


def _sample_job(**overrides):
    data = dict(
        id="job-1",
        title="Backend Engineer",
        company="Acme Corp",
        required_skills=["Python", "FastAPI"],
        nice_to_have_skills=["SQL"],
        minimum_years_experience=4,
        salary_min=85000,
        salary_max=100000,
        location="Berlin",
        remote_allowed=True,
        industries=["FinTech"],
    )
    data.update(overrides)
    return JobPosting(**data)


def test_full_match_scores_high() -> None:
    candidate = _sample_candidate()
    job = _sample_job()

    engine = MatchingEngine()
    matches = engine.match_candidates_to_jobs([candidate], [job], top_n=1)

    assert matches[0].candidate.id == candidate.id
    assert len(matches[0].matches) == 1

    top_match = matches[0].matches[0]
    assert top_match.job.id == job.id
    assert top_match.breakdown.skills == 1.0
    assert top_match.score >= 0.85


def test_remote_mismatch_penalizes_location_score() -> None:
    candidate = _sample_candidate(open_to_remote=False, preferred_locations=["Paris"])
    job = _sample_job(location=None)

    engine = MatchingEngine()
    scored = engine.match_candidates_to_jobs([candidate], [job], top_n=1)[0].matches[0]

    assert scored.breakdown.location < 0.5
    assert scored.score < 0.8


def test_better_skill_alignment_ranks_higher() -> None:
    candidate = _sample_candidate(skills=["Python", "Django", "SQL", "Docker"])

    close_match = _sample_job(id="job-close", required_skills=["Python", "Django"], nice_to_have_skills=["Docker"])
    weak_match = _sample_job(
        id="job-weak",
        required_skills=["Go", "Kubernetes"],
        nice_to_have_skills=["Rust"],
    )

    engine = MatchingEngine()
    matches = engine.match_candidates_to_jobs([candidate], [close_match, weak_match], top_n=2)

    job_ids = [match.job.id for match in matches[0].matches]
    assert job_ids == ["job-close", "job-weak"]
    assert matches[0].matches[0].score > matches[0].matches[1].score


def test_custom_weights_modify_results() -> None:
    candidate = _sample_candidate(skills=["Python"], desired_salary=120000)
    job = _sample_job(required_skills=["Python"], salary_max=100000)

    engine_default = MatchingEngine()
    engine_salary_focus = MatchingEngine(MatchingWeights(skills=0.3, experience=0.1, salary=0.4, location=0.1, industry=0.1))

    default_score = engine_default.match_candidates_to_jobs([candidate], [job])[0].matches[0].score
    salary_weighted_score = engine_salary_focus.match_candidates_to_jobs([candidate], [job])[0].matches[0].score

    assert salary_weighted_score < default_score
