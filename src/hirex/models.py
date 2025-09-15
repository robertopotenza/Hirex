"""Data models for the Hirex matching platform."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, validator


class CandidateProfile(BaseModel):
    """Represents a job seeker profile."""

    id: str = Field(..., description="Unique identifier for the candidate")
    full_name: str = Field(..., description="Display name for the candidate")
    years_experience: int = Field(
        ..., ge=0, description="Total number of professional experience years"
    )
    skills: List[str] = Field(
        default_factory=list,
        description="List of skills or technologies the candidate is comfortable with",
    )
    desired_salary: Optional[int] = Field(
        default=None,
        ge=0,
        description="Annual salary expectation in the same unit as job postings",
    )
    preferred_locations: List[str] = Field(
        default_factory=list,
        description="Candidate preferred work locations (city, country, etc.)",
    )
    open_to_remote: bool = Field(
        default=True, description="Whether the candidate is open to remote positions"
    )
    industries: List[str] = Field(
        default_factory=list,
        description="Industries the candidate has prior experience in",
    )

    @validator("skills", "preferred_locations", "industries", each_item=True)
    def _strip_values(cls, value: str) -> str:
        return value.strip()


class JobPosting(BaseModel):
    """Represents a job offer."""

    id: str = Field(..., description="Unique identifier for the job")
    title: str = Field(..., description="Title or name of the job role")
    company: Optional[str] = Field(
        default=None, description="Name of the company advertising the job"
    )
    required_skills: List[str] = Field(
        default_factory=list,
        description="Skills that are mandatory for the position",
    )
    nice_to_have_skills: List[str] = Field(
        default_factory=list, description="Skills that are a bonus for the position"
    )
    minimum_years_experience: int = Field(
        0,
        ge=0,
        description="Minimum experience expected for the role",
    )
    salary_min: Optional[int] = Field(
        default=None,
        ge=0,
        description="Lower bound of the salary range for the position",
    )
    salary_max: Optional[int] = Field(
        default=None,
        ge=0,
        description="Upper bound of the salary range for the position",
    )
    location: Optional[str] = Field(
        default=None, description="Primary location where the job is based"
    )
    remote_allowed: bool = Field(
        default=True, description="Whether the job supports remote work"
    )
    industries: List[str] = Field(
        default_factory=list,
        description="Industries associated with the job or company",
    )

    @validator("required_skills", "nice_to_have_skills", "industries")
    def _strip_and_dedupe(cls, values: List[str]) -> List[str]:
        seen: Dict[str, None] = {}
        ordered_unique = []
        for item in values:
            normalized = item.strip()
            if normalized and normalized.lower() not in seen:
                ordered_unique.append(normalized)
                seen[normalized.lower()] = None
        return ordered_unique

    @validator("salary_max")
    def _ensure_salary_range(
        cls, salary_max: Optional[int], values: Dict[str, Optional[int]]
    ) -> Optional[int]:
        salary_min = values.get("salary_min")
        if salary_max is not None and salary_min is not None:
            if salary_max < salary_min:
                raise ValueError("salary_max cannot be lower than salary_min")
        return salary_max


class MatchBreakdown(BaseModel):
    """Score decomposition used in responses."""

    skills: float
    experience: float
    salary: float
    location: float
    industry: float

    def total(self, weights: "MatchingWeights") -> float:
        return (
            self.skills * weights.skills
            + self.experience * weights.experience
            + self.salary * weights.salary
            + self.location * weights.location
            + self.industry * weights.industry
        ) / weights.total_weight


class JobMatch(BaseModel):
    job: JobPosting
    score: float
    breakdown: MatchBreakdown


class CandidateMatches(BaseModel):
    candidate: CandidateProfile
    matches: List[JobMatch]


class MatchingWeights(BaseModel):
    """Weights applied to each scoring component."""

    skills: float = 0.45
    experience: float = 0.2
    salary: float = 0.15
    location: float = 0.1
    industry: float = 0.1

    @property
    def total_weight(self) -> float:
        return self.skills + self.experience + self.salary + self.location + self.industry


__all__ = [
    "CandidateMatches",
    "CandidateProfile",
    "JobMatch",
    "JobPosting",
    "MatchBreakdown",
    "MatchingWeights",
]
