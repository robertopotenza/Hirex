"""LinkedIn job scraping utilities for extracting job posting information."""

import re
import uuid
from typing import List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .models import JobPosting


class LinkedInJobScraper:
    """Scrapes LinkedIn job postings to extract job information."""
    
    def __init__(self):
        self.session = requests.Session()
        # Set a user agent to appear as a regular browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Common skill keywords for extraction
        self.skill_keywords = [
            'python', 'java', 'javascript', 'typescript', 'react', 'angular', 'vue', 
            'node.js', 'express', 'django', 'flask', 'fastapi', 'spring', 'sql',
            'postgresql', 'mysql', 'mongodb', 'redis', 'aws', 'azure', 'gcp',
            'docker', 'kubernetes', 'git', 'jenkins', 'terraform', 'ansible',
            'html', 'css', 'rest', 'api', 'microservices', 'agile', 'scrum',
            'machine learning', 'ml', 'ai', 'data science', 'analytics'
        ]
    
    def scrape_job_posting(self, url: str) -> JobPosting:
        """Scrape a LinkedIn job posting URL and extract job information."""
        if not self._is_valid_linkedin_url(url):
            raise ValueError(f"Invalid LinkedIn job URL: {url}")
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch job posting: {str(e)}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract job information
        title = self._extract_title(soup)
        company = self._extract_company(soup)
        location = self._extract_location(soup)
        description = self._extract_description(soup)
        
        # Parse description for additional details
        required_skills, nice_to_have_skills = self._extract_skills(description)
        minimum_years_experience = self._extract_experience_requirement(description)
        salary_min, salary_max = self._extract_salary(description)
        remote_allowed = self._extract_remote_info(description, location)
        industries = self._extract_industries(description, company)
        
        # Generate unique ID
        job_id = str(uuid.uuid4())[:8]
        
        return JobPosting(
            id=job_id,
            title=title,
            company=company,
            required_skills=required_skills,
            nice_to_have_skills=nice_to_have_skills,
            minimum_years_experience=minimum_years_experience,
            salary_min=salary_min,
            salary_max=salary_max,
            location=location,
            remote_allowed=remote_allowed,
            industries=industries
        )
    
    def _is_valid_linkedin_url(self, url: str) -> bool:
        """Check if URL is a valid LinkedIn job posting URL."""
        try:
            parsed = urlparse(url)
            return (
                parsed.netloc.endswith('linkedin.com') and
                '/jobs/view/' in parsed.path
            )
        except Exception:
            return False
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract job title from the page."""
        # Try multiple selectors for job title
        selectors = [
            'h1.top-card-layout__title',
            'h1.topcard__title',
            'h1[data-test-id="job-title"]',
            '.job-details-jobs-unified-top-card__job-title h1',
            'h1'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        return "Unknown Position"
    
    def _extract_company(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company name from the page."""
        selectors = [
            '.topcard__org-name-link',
            '.top-card-layout__card .top-card-layout__entity-info a',
            'a[data-test-id="company-name"]',
            '.job-details-jobs-unified-top-card__company-name a'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element and element.get_text(strip=True):
                return element.get_text(strip=True)
        
        return None
    
    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract location from the page."""
        selectors = [
            '.topcard__flavor--bullet',
            '.top-card-layout__entity-info .topcard__flavor',
            '[data-test-id="job-location"]',
            '.job-details-jobs-unified-top-card__primary-description'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Filter out experience requirements and focus on location
                if any(word in text.lower() for word in ['city', 'state', 'country', 'remote']) or ',' in text:
                    return text
        
        return None
    
    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract job description from the page."""
        selectors = [
            '.description__text',
            '.job-details-jobs-unified-top-card__job-description',
            '.jobs-description-content__text',
            '.jobs-box__html-content'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        # Fallback: get all text content
        return soup.get_text()
    
    def _extract_skills(self, description: str) -> tuple[List[str], List[str]]:
        """Extract required and nice-to-have skills from job description."""
        description_lower = description.lower()
        found_skills = []
        
        # Find skills mentioned in the description
        for skill in self.skill_keywords:
            if skill.lower() in description_lower:
                found_skills.append(skill.title())
        
        # Split into required vs nice-to-have based on context
        required_skills = []
        nice_to_have_skills = []
        
        # Look for sections that indicate requirements vs preferences
        description_sections = description.split('\n')
        current_section_type = 'required'  # default
        
        for section in description_sections:
            section_lower = section.lower()
            
            # Detect section type
            if any(phrase in section_lower for phrase in ['required', 'must have', 'essential', 'qualifications']):
                current_section_type = 'required'
            elif any(phrase in section_lower for phrase in ['preferred', 'nice to have', 'bonus', 'plus']):
                current_section_type = 'nice_to_have'
            
            # Check for skills in this section
            for skill in found_skills:
                if skill.lower() in section_lower:
                    if current_section_type == 'required':
                        required_skills.append(skill)
                    else:
                        nice_to_have_skills.append(skill)
        
        # If no clear separation found, treat first half as required
        if not required_skills and not nice_to_have_skills:
            mid_point = len(found_skills) // 2
            required_skills = found_skills[:mid_point] if mid_point > 0 else found_skills[:3]
            nice_to_have_skills = found_skills[mid_point:] if mid_point > 0 else []
        
        # Remove duplicates while preserving order
        required_skills = list(dict.fromkeys(required_skills))
        nice_to_have_skills = list(dict.fromkeys(nice_to_have_skills))
        
        return required_skills, nice_to_have_skills
    
    def _extract_experience_requirement(self, description: str) -> int:
        """Extract minimum years of experience from job description."""
        # Look for patterns like "3+ years", "2-5 years", "minimum 4 years"
        patterns = [
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
            r'minimum\s*(?:of\s*)?(\d+)\s*years?',
            r'(\d+)\s*to\s*\d+\s*years?',
            r'(\d+)\s*-\s*\d+\s*years?',
        ]
        
        description_lower = description.lower()
        for pattern in patterns:
            matches = re.findall(pattern, description_lower)
            if matches:
                return int(matches[0])
        
        # Default to 0 if no experience requirement found
        return 0
    
    def _extract_salary(self, description: str) -> tuple[Optional[int], Optional[int]]:
        """Extract salary range from job description."""
        # Look for salary patterns
        patterns = [
            r'\$(\d{1,3}(?:,\d{3})*)\s*-\s*\$(\d{1,3}(?:,\d{3})*)',
            r'\$(\d{1,3}(?:,\d{3})*)\s*to\s*\$(\d{1,3}(?:,\d{3})*)',
            r'(\d{1,3}(?:,\d{3})*)\s*-\s*(\d{1,3}(?:,\d{3})*)\s*(?:USD|dollars?)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, description)
            if matches:
                min_sal, max_sal = matches[0]
                # Remove commas and convert to int
                min_salary = int(min_sal.replace(',', ''))
                max_salary = int(max_sal.replace(',', ''))
                return min_salary, max_salary
        
        return None, None
    
    def _extract_remote_info(self, description: str, location: Optional[str]) -> bool:
        """Determine if remote work is allowed."""
        description_lower = description.lower()
        location_lower = location.lower() if location else ""
        
        remote_indicators = [
            'remote', 'work from home', 'telecommute', 'distributed',
            'anywhere', 'location independent'
        ]
        
        return any(indicator in description_lower or indicator in location_lower 
                  for indicator in remote_indicators)
    
    def _extract_industries(self, description: str, company: Optional[str]) -> List[str]:
        """Extract relevant industries from job description and company."""
        industries = []
        description_lower = description.lower()
        
        # Common industry keywords
        industry_map = {
            'fintech': ['fintech', 'financial technology', 'banking', 'finance'],
            'saas': ['saas', 'software as a service', 'cloud software'],
            'healthcare': ['healthcare', 'medical', 'health tech', 'biotech'],
            'e-commerce': ['e-commerce', 'ecommerce', 'retail', 'marketplace'],
            'education': ['education', 'edtech', 'learning', 'university'],
            'gaming': ['gaming', 'games', 'entertainment'],
            'automotive': ['automotive', 'transportation', 'mobility'],
            'real estate': ['real estate', 'property', 'housing'],
        }
        
        for industry, keywords in industry_map.items():
            if any(keyword in description_lower for keyword in keywords):
                industries.append(industry.title())
        
        return industries