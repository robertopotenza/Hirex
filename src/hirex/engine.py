"""Core matching logic for the Hirex platform."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .models import (
    CandidateMatches,
    CandidateProfile,
    JobMatch,
    JobPosting,
    MatchBreakdown,
    MatchingWeights,
)


@dataclass
class ScoredMatch:
    """Internal representation that couples a job with the score breakdown."""

    job: JobPosting
    score: float
    breakdown: MatchBreakdown


class MatchingEngine:
    """Scores candidates against jobs using weighted heuristics."""

    def __init__(self, weights: MatchingWeights | None = None) -> None:
        self.weights = weights or MatchingWeights()

    def match_candidates_to_jobs(
        self,
        candidates: Sequence[CandidateProfile],
        jobs: Sequence[JobPosting],
        *,
        top_n: int = 3,
    ) -> List[CandidateMatches]:
        """Return the top job matches for each candidate.

        Args:
            candidates: Profiles of the job seekers to evaluate.
            jobs: Available job postings to compare against.
            top_n: Maximum number of matches to return per candidate.

        Returns:
            A list of :class:`CandidateMatches` with ranked job suggestions.
        """

        recommendations: List[CandidateMatches] = []
        for candidate in candidates:
            scored_jobs = [
                self._score_candidate_for_job(candidate=candidate, job=job)
                for job in jobs
            ]
            scored_jobs.sort(key=lambda match: match.score, reverse=True)
            top_matches = [
                JobMatch(job=match.job, score=match.score, breakdown=match.breakdown)
                for match in scored_jobs[: max(0, top_n)]
            ]
            recommendations.append(CandidateMatches(candidate=candidate, matches=top_matches))
        return recommendations

    def _score_candidate_for_job(
        self, candidate: CandidateProfile, job: JobPosting
    ) -> ScoredMatch:
        breakdown = MatchBreakdown(
            skills=self._skill_score(candidate.skills, job.required_skills, job.nice_to_have_skills),
            experience=self._experience_score(
                candidate.years_experience, job.minimum_years_experience
            ),
            salary=self._salary_score(candidate.desired_salary, job.salary_min, job.salary_max),
            location=self._location_score(
                candidate.preferred_locations,
                candidate.open_to_remote,
                job.location,
                job.remote_allowed,
            ),
            industry=self._industry_score(candidate.industries, job.industries),
        )
        score = breakdown.total(self.weights)
        return ScoredMatch(job=job, score=round(score, 4), breakdown=breakdown)

    def _skill_score(
        self,
        candidate_skills: Iterable[str],
        required_skills: Iterable[str],
        nice_to_have_skills: Iterable[str],
    ) -> float:
        cand_set = _normalized_set(candidate_skills)
        required_set = _normalized_set(required_skills)
        optional_set = _normalized_set(nice_to_have_skills)

        if not cand_set and required_set:
            return 0.0
        if not required_set:
            return 1.0 if cand_set else 0.5

        matched_required = cand_set & required_set
        base_score = len(matched_required) / len(required_set)

        if optional_set:
            matched_optional = cand_set & optional_set
            optional_bonus = (len(matched_optional) / len(optional_set)) * 0.3
        else:
            optional_bonus = 0.0

        return min(1.0, base_score + optional_bonus)

    def _experience_score(
        self, candidate_years: int, job_minimum_years: int
    ) -> float:
        if job_minimum_years <= 0:
            return 1.0

        if candidate_years >= job_minimum_years:
            surplus = candidate_years - job_minimum_years
            surplus_ratio = surplus / max(job_minimum_years, 1)
            return min(1.0, 0.7 + min(surplus_ratio, 1.0) * 0.3)

        deficit = job_minimum_years - candidate_years
        penalty = deficit / (job_minimum_years + 1)
        return max(0.0, 0.7 - penalty)

    def _salary_score(
        self,
        desired_salary: int | None,
        salary_min: int | None,
        salary_max: int | None,
    ) -> float:
        if desired_salary is None or (salary_min is None and salary_max is None):
            return 1.0

        score = 1.0
        if salary_max is not None and desired_salary > salary_max:
            diff = desired_salary - salary_max
            score -= min(1.0, diff / max(salary_max, 1))

        if salary_min is not None and desired_salary < salary_min:
            diff = salary_min - desired_salary
            score -= min(0.4, diff / max(salary_min, 1) * 0.4)

        return max(0.0, score)

    def _location_score(
        self,
        preferred_locations: Iterable[str],
        open_to_remote: bool,
        job_location: str | None,
        job_remote: bool,
    ) -> float:
        preferred = _normalized_set(preferred_locations)
        job_loc = job_location.strip().lower() if job_location else None

        if job_remote and open_to_remote:
            return 1.0

        if job_loc and job_loc in preferred:
            return 1.0

        if not preferred:
            # Candidate is flexible; reward jobs that offer remote or specify a location
            return 0.8 if job_loc else 1.0

        # Candidate has preferences but this job does not match.
        return 0.2 if job_loc else 0.4

    def _industry_score(
        self, candidate_industries: Iterable[str], job_industries: Iterable[str]
    ) -> float:
        candidate_set = _normalized_set(candidate_industries)
        job_set = _normalized_set(job_industries)

        if not candidate_set and not job_set:
            return 0.5
        if not candidate_set:
            return 0.6
        if not job_set:
            return 0.7

        intersection = candidate_set & job_set
        return len(intersection) / len(job_set)


def _normalized_set(values: Iterable[str]) -> set[str]:
    return {value.strip().lower() for value in values if value and value.strip()}


__all__ = ["MatchingEngine"]
