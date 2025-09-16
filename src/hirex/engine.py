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
    RoleExperience,
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
        # Compute role-level relevance for this specific job
        relevant_years, recent_relevant_years = self._compute_relevant_years(candidate, job)
        
        breakdown = MatchBreakdown(
            skills=self._skill_score(candidate.skills, job.required_skills, job.nice_to_have_skills),
            experience=self._experience_score(
                candidate.years_experience, job.minimum_years_experience, relevant_years, recent_relevant_years
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
        self, candidate_years: int, job_minimum_years: int, 
        relevant_years: float = None, recent_relevant_years: float = None
    ) -> float:
        if job_minimum_years <= 0:
            return 1.0

        # Use blended years if relevance data is available
        if relevant_years is not None and recent_relevant_years is not None:
            # Prefer recent relevant experience over total relevant experience
            blended_years = 0.75 * recent_relevant_years + 0.25 * relevant_years
        else:
            # Fallback to traditional experience scoring
            blended_years = float(candidate_years)

        if blended_years >= job_minimum_years:
            surplus = blended_years - job_minimum_years
            surplus_ratio = surplus / max(job_minimum_years, 1)
            return min(1.0, 0.7 + min(surplus_ratio, 1.0) * 0.3)  # Keep original baseline

        deficit = job_minimum_years - blended_years
        penalty = deficit / (job_minimum_years + 1)
        return max(0.0, 0.7 - penalty)
    
    def _compute_relevant_years(self, candidate: CandidateProfile, job: JobPosting) -> tuple[float, float]:
        """Compute role-level relevance for a specific job."""
        if not candidate.roles:
            # Fallback to basic experience if no roles available
            # Assume all experience is recent for backward compatibility
            years = float(candidate.years_experience)
            recent = min(years, 5.0)  # Cap recent at 5 years window
            return years, recent
        
        relevant_years = 0.0
        recent_relevant_years = 0.0
        recent_cutoff_years = 5  # Recent window
        
        # Normalize job requirements for matching
        job_title_tokens = _normalized_set(job.title.split())
        job_skills = _normalized_set(job.required_skills)
        candidate_skills = _normalized_set(candidate.skills)
        
        for role in candidate.roles:
            # Compute title match (exact token overlap)
            role_title_tokens = _normalized_set(role.title.split())
            title_match = 1.0 if job_title_tokens & role_title_tokens else 0.0
            
            # Enhanced skill overlap computation
            skill_overlap = 0.0
            if job_skills:
                # Base skill overlap from candidate's global skills
                base_overlap = len(candidate_skills & job_skills) / len(job_skills)
                
                # Role-specific skill bonus: extract skills from role title and description
                role_text = role.title.lower()
                if role.description:
                    role_text += " " + role.description.lower()
                
                role_specific_skills = set()
                for skill in job_skills:
                    if skill in role_text:
                        role_specific_skills.add(skill)
                
                # Boost overlap if role mentions specific job skills
                role_skill_bonus = len(role_specific_skills) / len(job_skills) if job_skills else 0.0
                
                # Combine base overlap with role-specific bonus (weighted)
                skill_overlap = 0.7 * base_overlap + 0.3 * role_skill_bonus
            
            # Domain relevance: boost if role and job are in similar domains
            domain_boost = 0.0
            if self._roles_in_similar_domain(role, job):
                domain_boost = 0.2
            
            # Role relevance is the maximum of title match and skill overlap, plus domain boost
            role_relevance = min(1.0, max(title_match, skill_overlap) + domain_boost)
            
            # Add to relevant years weighted by relevance
            relevant_years += role.duration_years * role_relevance
            
            # Compute recent relevant years (overlap with last N years)
            if role.start_year is not None:
                from datetime import datetime
                current_year = datetime.now().year
                recent_start = max(role.start_year, current_year - recent_cutoff_years)
                recent_end = min(role.end_year or current_year, current_year)
                
                if recent_start <= recent_end:
                    recent_duration = recent_end - recent_start
                    recent_relevant_years += recent_duration * role_relevance
            else:
                # If no start year, assume the role overlaps with recent period proportionally
                if role.duration_years <= recent_cutoff_years:
                    recent_relevant_years += role.duration_years * role_relevance
        
        return relevant_years, recent_relevant_years
    
    def _roles_in_similar_domain(self, role: RoleExperience, job: JobPosting) -> bool:
        """Check if a role and job are in similar domains."""
        role_text = (role.title + " " + (role.description or "")).lower()
        job_text = (job.title + " " + " ".join(job.required_skills)).lower()
        
        # Define domain keywords
        domains = {
            'backend': ['backend', 'api', 'server', 'database', 'microservice'],
            'frontend': ['frontend', 'ui', 'react', 'angular', 'vue', 'html', 'css'],
            'data': ['data', 'analytics', 'science', 'analyst', 'ml', 'ai'],
            'devops': ['devops', 'infrastructure', 'cloud', 'aws', 'docker', 'kubernetes'],
            'mobile': ['mobile', 'ios', 'android', 'app'],
        }
        
        role_domains = set()
        job_domains = set()
        
        for domain, keywords in domains.items():
            if any(keyword in role_text for keyword in keywords):
                role_domains.add(domain)
            if any(keyword in job_text for keyword in keywords):
                job_domains.add(domain)
        
        return bool(role_domains & job_domains)

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
