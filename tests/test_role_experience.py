"""Tests for role-level experience parsing and relevance-aware scoring."""

from __future__ import annotations

import pytest

from hirex.engine import MatchingEngine
from hirex.models import CandidateProfile, JobPosting, RoleExperience
from hirex.resume_parser import ResumeParser


def test_role_experience_model():
    """Test that RoleExperience model works correctly."""
    role = RoleExperience(
        title="Senior Python Developer",
        duration_years=3.5,
        description="Developed web applications using Django",
        start_year=2020,
        end_year=2023
    )
    
    assert role.title == "Senior Python Developer"
    assert role.duration_years == 3.5
    assert role.start_year == 2020
    assert role.end_year == 2023


def test_candidate_profile_with_roles():
    """Test that CandidateProfile accepts role information."""
    roles = [
        RoleExperience(
            title="Senior Developer",
            duration_years=2.0,
            description="Built REST APIs",
            start_year=2022,
            end_year=None
        )
    ]
    
    candidate = CandidateProfile(
        id="test-1",
        full_name="John Doe",
        years_experience=5,
        skills=["Python", "Django"],
        roles=roles,
        relevant_years=4.5,
        recent_relevant_years=2.0,
        seniority="Senior"
    )
    
    assert len(candidate.roles) == 1
    assert candidate.roles[0].title == "Senior Developer"
    assert candidate.relevant_years == 4.5
    assert candidate.recent_relevant_years == 2.0
    assert candidate.seniority == "Senior"


def test_resume_parser_extracts_roles():
    """Test that resume parser can extract role information."""
    parser = ResumeParser()
    
    sample_resume = """
    John Smith
    Software Engineer
    
    Experience:
    Senior Python Developer
    January 2020 - Present
    • Developed microservices using FastAPI
    • Led a team of 3 developers
    • Built CI/CD pipelines
    
    Junior Software Developer
    2018 - 2020
    • Created REST APIs using Flask
    • Worked with PostgreSQL databases
    
    Skills: Python, FastAPI, Flask, PostgreSQL, Docker, AWS
    """
    
    roles = parser._extract_roles(sample_resume)
    
    assert len(roles) >= 1  # Should extract at least one role
    
    # Check that roles have reasonable data
    for role in roles:
        assert role.title is not None
        assert role.duration_years > 0
    
    # Test seniority inference
    seniority = parser._infer_seniority(roles)
    assert seniority is not None


def test_matching_engine_computes_relevant_years():
    """Test that matching engine computes role-level relevance."""
    # Create a candidate with role-level experience
    roles = [
        RoleExperience(
            title="Python Developer",
            duration_years=3.0,
            description="Built web applications with Django and Flask",
            start_year=2021,
            end_year=None
        ),
        RoleExperience(
            title="Java Developer", 
            duration_years=2.0,
            description="Developed enterprise applications with Spring",
            start_year=2019,
            end_year=2021
        )
    ]
    
    candidate = CandidateProfile(
        id="test-candidate",
        full_name="Alex Developer",
        years_experience=5,
        skills=["Python", "Django", "Flask", "Java", "Spring"],
        roles=roles
    )
    
    # Create a Python job posting
    python_job = JobPosting(
        id="python-job",
        title="Python Backend Developer",
        required_skills=["Python", "Django"],
        minimum_years_experience=2
    )
    
    # Create a Java job posting
    java_job = JobPosting(
        id="java-job", 
        title="Java Developer",
        required_skills=["Java", "Spring"],
        minimum_years_experience=2
    )
    
    engine = MatchingEngine()
    
    # Test relevance computation for Python job
    relevant_py, recent_py = engine._compute_relevant_years(candidate, python_job)
    assert relevant_py > 0  # Should have some relevant experience
    
    # Test relevance computation for Java job  
    relevant_java, recent_java = engine._compute_relevant_years(candidate, java_job)
    assert relevant_java > 0  # Should have some relevant experience
    
    # Python role should be more relevant for Python job due to title match
    assert relevant_py >= relevant_java


def test_experience_scoring_with_relevance():
    """Test that experience scoring uses relevance-aware computation."""
    # Candidate with mixed experience
    roles = [
        RoleExperience(
            title="Python Developer",
            duration_years=2.0,
            description="Web development with Django",
            start_year=2022,
            end_year=None
        ),
        RoleExperience(
            title="Data Analyst",
            duration_years=3.0, 
            description="Excel and SQL analysis",
            start_year=2019,
            end_year=2022
        )
    ]
    
    candidate = CandidateProfile(
        id="mixed-candidate",
        full_name="Mixed Experience",
        years_experience=5,
        skills=["Python", "Django", "SQL", "Excel"],
        roles=roles
    )
    
    # Python job that matches recent role
    python_job = JobPosting(
        id="python-job",
        title="Python Developer", 
        required_skills=["Python", "Django"],
        minimum_years_experience=3
    )
    
    # Data analysis job that matches older role
    analyst_job = JobPosting(
        id="analyst-job",
        title="Data Analyst",
        required_skills=["SQL", "Excel"], 
        minimum_years_experience=3
    )
    
    engine = MatchingEngine()
    
    # Score for both jobs
    python_matches = engine.match_candidates_to_jobs([candidate], [python_job], top_n=1)
    analyst_matches = engine.match_candidates_to_jobs([candidate], [analyst_job], top_n=1)
    
    python_score = python_matches[0].matches[0].breakdown.experience
    analyst_score = analyst_matches[0].matches[0].breakdown.experience
    
    # Both should have reasonable scores
    assert python_score > 0.0
    assert analyst_score > 0.0
    
    # Python job should score higher due to recent relevant experience
    assert python_score >= analyst_score


def test_backward_compatibility_with_no_roles():
    """Test that candidates without roles still work correctly."""
    # Traditional candidate without roles
    candidate = CandidateProfile(
        id="traditional",
        full_name="Traditional Candidate", 
        years_experience=5,
        skills=["Python", "FastAPI"]
    )
    
    job = JobPosting(
        id="test-job",
        title="Backend Developer",
        required_skills=["Python"],
        minimum_years_experience=3
    )
    
    engine = MatchingEngine()
    matches = engine.match_candidates_to_jobs([candidate], [job], top_n=1)
    
    # Should work and return reasonable score
    assert len(matches) == 1
    assert len(matches[0].matches) == 1
    assert matches[0].matches[0].score > 0.5


def test_seniority_inference():
    """Test seniority inference from role titles."""
    parser = ResumeParser()
    
    # Test senior level
    senior_roles = [
        RoleExperience(title="Senior Software Engineer", duration_years=3.0),
        RoleExperience(title="Developer", duration_years=2.0)
    ]
    assert parser._infer_seniority(senior_roles) == "Senior"
    
    # Test lead level
    lead_roles = [
        RoleExperience(title="Lead Developer", duration_years=2.0)
    ]
    assert parser._infer_seniority(lead_roles) == "Lead"
    
    # Test junior level
    junior_roles = [
        RoleExperience(title="Junior Developer", duration_years=1.0)
    ]
    assert parser._infer_seniority(junior_roles) == "Junior"
    
    # Test experience-based inference
    long_exp_roles = [
        RoleExperience(title="Software Engineer", duration_years=10.0)
    ]
    assert parser._infer_seniority(long_exp_roles) == "Senior"


def test_recent_years_computation():
    """Test computation of recent relevant years."""
    parser = ResumeParser()
    
    roles = [
        RoleExperience(
            title="Current Role",
            duration_years=3.0,
            start_year=2022,
            end_year=None  # Current
        ),
        RoleExperience(
            title="Old Role", 
            duration_years=2.0,
            start_year=2015,
            end_year=2017  # Outside recent window
        )
    ]
    
    recent_years = parser._compute_recent_years(roles, window_years=5)
    
    # Should only count the recent role
    assert recent_years >= 2.0  # At least 2 years from current role
    assert recent_years <= 5.0  # Can't exceed window


if __name__ == "__main__":
    pytest.main([__file__])