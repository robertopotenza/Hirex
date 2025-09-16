"""Resume parsing utilities for extracting candidate profile information."""

import re
import uuid
from io import BytesIO
from typing import List, Optional

import PyPDF2
from docx import Document

from .models import CandidateProfile


class ResumeParser:
    """Parses resumes from PDF and DOCX files to extract candidate information."""
    
    def __init__(self):
        # Common skills patterns for extraction
        self.skill_patterns = [
            r'\b(?:python|java|javascript|typescript|react|angular|vue|node\.?js|express|django|flask|fastapi)\b',
            r'\b(?:sql|postgresql|mysql|mongodb|redis|elasticsearch|nosql)\b',
            r'\b(?:aws|azure|gcp|docker|kubernetes|git|jenkins|terraform|ansible)\b',
            r'\b(?:html|css|rest|api|microservices|agile|scrum|devops|ci/cd)\b',
            r'\b(?:machine learning|ml|ai|data science|analytics|pandas|numpy|sklearn)\b',
        ]
        
    def parse_resume(self, file_content: bytes, filename: str) -> CandidateProfile:
        """Parse resume file and extract candidate profile information."""
        text = self._extract_text(file_content, filename)
        
        # Extract basic information
        full_name = self._extract_name(text, filename)
        years_experience = self._extract_experience(text)
        skills = self._extract_skills(text)
        
        # Generate unique ID
        candidate_id = str(uuid.uuid4())[:8]
        
        return CandidateProfile(
            id=candidate_id,
            full_name=full_name,
            years_experience=years_experience,
            skills=skills,
            # Set reasonable defaults for other fields
            desired_salary=None,
            preferred_locations=[],
            open_to_remote=True,
            industries=[]
        )
    
    def _extract_text(self, file_content: bytes, filename: str) -> str:
        """Extract text content from PDF or DOCX file."""
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return self._extract_text_from_pdf(file_content)
        elif filename_lower.endswith('.docx'):
            return self._extract_text_from_docx(file_content)
        else:
            raise ValueError(f"Unsupported file format: {filename}")
    
    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF file."""
        try:
            reader = PyPDF2.PdfReader(BytesIO(file_content))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    
    def _extract_text_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(BytesIO(file_content))
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {str(e)}")
    
    def _extract_name(self, text: str, filename: str) -> str:
        """Extract candidate name from resume text."""
        lines = text.strip().split('\n')
        
        # Try to find name in first few lines
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 0 and len(line.split()) >= 2:
                # Check if line looks like a name (contains letters and spaces)
                if re.match(r'^[A-Za-z\s\-\'\.]+$', line):
                    return line
        
        # Fallback: use filename without extension
        name_from_file = filename.split('.')[0].replace('_', ' ').replace('-', ' ')
        if name_from_file:
            return name_from_file.title()
        
        return "Unknown Candidate"
    
    def _extract_experience(self, text: str) -> int:
        """Extract years of experience from resume text."""
        # Look for patterns like "5 years", "3+ years", "2-4 years"
        patterns = [
            r'(\d+)\+?\s*years?\s*(?:of\s*)?experience',
            r'(\d+)\s*years?\s*in',
            r'(\d+)\s*years?\s*working',
            r'experience[:\s]*(\d+)\s*years?',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                # Return the highest number found
                return max(int(match) for match in matches)
        
        # Fallback: count job positions or education timeline
        lines = text.lower().split('\n')
        job_indicators = ['experience', 'employment', 'work history', 'professional']
        education_years = []
        
        for line in lines:
            # Look for graduation years
            year_matches = re.findall(r'(19|20)\d{2}', line)
            if any(indicator in line for indicator in job_indicators) and year_matches:
                education_years.extend(int(year) for year in year_matches)
        
        if education_years:
            # Estimate experience as years since earliest mentioned year
            current_year = 2024
            earliest_year = min(education_years)
            return max(0, current_year - earliest_year - 2)  # Subtract 2 for education
        
        # Default fallback
        return 1
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract technical skills from resume text."""
        skills = []
        text_lower = text.lower()
        
        # Apply skill patterns
        for pattern in self.skill_patterns:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            skills.extend(matches)
        
        # Clean and deduplicate skills
        cleaned_skills = []
        seen = set()
        
        for skill in skills:
            skill = skill.strip().title()
            skill_key = skill.lower()
            if skill_key not in seen and skill:
                cleaned_skills.append(skill)
                seen.add(skill_key)
        
        # If no skills found, try to extract from dedicated sections
        if not cleaned_skills:
            skills_section = self._extract_skills_section(text)
            if skills_section:
                cleaned_skills = skills_section
        
        return cleaned_skills[:15]  # Limit to top 15 skills
    
    def _extract_skills_section(self, text: str) -> List[str]:
        """Extract skills from dedicated skills sections."""
        lines = text.split('\n')
        skills = []
        in_skills_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Detect start of skills section
            if any(keyword in line_lower for keyword in ['skills', 'technologies', 'technical']):
                in_skills_section = True
                continue
            
            # Stop if we hit another section
            if in_skills_section and line_lower.startswith(('experience', 'education', 'projects')):
                break
            
            # Extract skills from the section
            if in_skills_section and line.strip():
                # Split by common delimiters
                line_skills = re.split(r'[,;|\n]', line)
                for skill in line_skills:
                    skill = skill.strip()
                    if len(skill) > 1 and len(skill) < 30:  # Reasonable skill length
                        skills.append(skill.title())
        
        return skills[:10]  # Limit extracted skills