"""Tests for the new resume parsing and job matching functionality."""

import os
import sys
from pathlib import Path

# Add the src directory to the path for imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.hirex.resume_parser import ResumeParser
from src.hirex.job_scraper import LinkedInJobScraper


def test_resume_parser_basic_functionality():
    """Test basic resume parsing functionality."""
    parser = ResumeParser()
    
    # Test with a simple text resume (treating as if from file)
    sample_text = """
    John Smith
    Software Engineer
    
    Skills: Python, Django, PostgreSQL, AWS, Docker, React
    Experience: 5 years in software development
    """
    
    # Since we can't easily create PDF/DOCX for testing, we'll test the text extraction logic
    skills = parser._extract_skills(sample_text)
    experience = parser._extract_experience(sample_text)
    name = parser._extract_name(sample_text, "john_smith_resume.pdf")
    
    assert len(skills) > 0
    assert "Python" in skills or "python" in [s.lower() for s in skills]
    assert experience >= 0
    assert "John Smith" in name or "john smith" in name.lower()


def test_linkedin_url_validation():
    """Test LinkedIn URL validation."""
    scraper = LinkedInJobScraper()
    
    # Test valid URLs
    valid_urls = [
        "https://www.linkedin.com/jobs/view/1234567890",
        "https://linkedin.com/jobs/view/9876543210",
    ]
    
    for url in valid_urls:
        assert scraper._is_valid_linkedin_url(url), f"URL should be valid: {url}"
    
    # Test invalid URLs
    invalid_urls = [
        "https://google.com",
        "https://linkedin.com/profile/someone",
        "not-a-url",
        "https://www.linkedin.com/jobs/search/",
    ]
    
    for url in invalid_urls:
        assert not scraper._is_valid_linkedin_url(url), f"URL should be invalid: {url}"


def test_skill_extraction_patterns():
    """Test skill extraction from job descriptions."""
    scraper = LinkedInJobScraper()
    
    description = """
    We are looking for a Senior Python Developer with experience in:
    - Python, Django, FastAPI
    - PostgreSQL, MongoDB databases
    - AWS, Docker, Kubernetes
    - React, JavaScript for frontend
    
    Required skills:
    - 5+ years Python experience
    - Strong SQL knowledge
    - Experience with microservices
    
    Nice to have:
    - Machine Learning experience
    - TypeScript knowledge
    """
    
    required_skills, nice_to_have_skills = scraper._extract_skills(description)
    
    # Should find some skills
    assert len(required_skills) > 0 or len(nice_to_have_skills) > 0
    
    # Test experience extraction
    min_experience = scraper._extract_experience_requirement(description)
    assert min_experience >= 0  # Should extract some experience requirement


if __name__ == "__main__":
    test_resume_parser_basic_functionality()
    test_linkedin_url_validation()
    test_skill_extraction_patterns()
    print("All tests passed!")