"""Resume parsing utilities for extracting candidate profile information."""

import re
import uuid
from datetime import datetime
from io import BytesIO
from typing import List, Optional

import PyPDF2
from docx import Document

from .models import CandidateProfile, RoleExperience


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
        
        # Extract role-level experience
        roles = self._extract_roles(text)
        
        # If role extraction failed, create a fallback role from basic experience
        if not roles and years_experience > 0:
            roles = [RoleExperience(
                title="Unknown Role",
                duration_years=float(years_experience),
                description=None,
                start_year=None,
                end_year=None
            )]
        
        # Compute seniority from roles
        seniority = self._infer_seniority(roles)
        
        # Compute default relevant years (will be refined by engine per job)
        total_years = sum(role.duration_years for role in roles)
        recent_years = self._compute_recent_years(roles)
        
        # Generate unique ID
        candidate_id = str(uuid.uuid4())[:8]
        
        return CandidateProfile(
            id=candidate_id,
            full_name=full_name,
            years_experience=years_experience,
            skills=skills,
            roles=roles,
            relevant_years=total_years,  # Default to all years; engine will refine per job
            recent_relevant_years=recent_years,
            seniority=seniority,
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
    
    def _extract_roles(self, text: str) -> List[RoleExperience]:
        """Extract role-level experience with date ranges from resume text."""
        roles = []
        lines = text.split('\n')
        current_year = datetime.now().year
        
        # Date patterns to match various formats
        date_patterns = [
            r'(\w+)\s+(\d{4})\s*[-–—]\s*(\w+)\s+(\d{4})',  # "Jan 2018 - Feb 2021"
            r'(\d{4})\s*[-–—]\s*(\d{4})',  # "2018 - 2021"
            r'(\w+)\s+(\d{4})\s*[-–—]\s*(present|current)',  # "Jan 2018 - Present"
            r'(\d{4})\s*[-–—]\s*(present|current)',  # "2018 - Present"
            r'(\d{4})\s*[-–—]\s*(\d{4})',  # "2018-2021"
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Look for date ranges in the line
            for pattern in date_patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                if matches:
                    # Found a date range, extract role info
                    match = matches[0]
                    start_year, end_year, duration = self._parse_date_range(match, current_year)
                    
                    if duration <= 0:
                        continue
                    
                    # Find the role title (previous non-empty line)
                    role_title = "Unknown Role"
                    for j in range(i - 1, max(-1, i - 5), -1):
                        prev_line = lines[j].strip()
                        if prev_line and not any(re.search(pat, prev_line, re.IGNORECASE) for pat in date_patterns):
                            role_title = prev_line
                            break
                    
                    # Find role description (following lines until next date or section)
                    description_lines = []
                    for j in range(i + 1, min(len(lines), i + 10)):
                        desc_line = lines[j].strip()
                        if not desc_line:
                            continue
                        if any(re.search(pat, desc_line, re.IGNORECASE) for pat in date_patterns):
                            break
                        if desc_line.lower().startswith(('education', 'skills', 'projects')):
                            break
                        description_lines.append(desc_line)
                    
                    description = ' '.join(description_lines) if description_lines else None
                    
                    roles.append(RoleExperience(
                        title=role_title,
                        duration_years=duration,
                        description=description,
                        start_year=start_year,
                        end_year=end_year
                    ))
                    break
        
        return roles
    
    def _parse_date_range(self, match: tuple, current_year: int) -> tuple[Optional[int], Optional[int], float]:
        """Parse a date range match and return start_year, end_year, and duration."""
        try:
            if len(match) == 4:  # "Jan 2018 - Feb 2021" format
                start_month, start_year_str, end_month, end_year_str = match
                start_year = int(start_year_str)
                if end_year_str.lower() in ['present', 'current']:
                    end_year = None
                    duration = current_year - start_year
                else:
                    end_year = int(end_year_str)
                    duration = end_year - start_year
            elif len(match) == 2:
                if match[1].lower() in ['present', 'current']:  # "2018 - Present" format
                    start_year = int(match[0])
                    end_year = None
                    duration = current_year - start_year
                else:  # "2018 - 2021" format
                    start_year = int(match[0])
                    end_year = int(match[1])
                    duration = end_year - start_year
            else:
                return None, None, 0.0
            
            return start_year, end_year, max(0.0, float(duration))
        except (ValueError, IndexError):
            return None, None, 0.0
    
    def _infer_seniority(self, roles: List[RoleExperience]) -> Optional[str]:
        """Infer seniority level from role titles."""
        if not roles:
            return None
        
        # Check most recent role first, then others
        all_titles = ' '.join(role.title.lower() for role in roles)
        
        if any(term in all_titles for term in ['lead', 'principal', 'architect', 'director', 'vp', 'head']):
            return 'Lead'
        elif any(term in all_titles for term in ['senior', 'sr']):
            return 'Senior'
        elif any(term in all_titles for term in ['junior', 'jr', 'associate', 'intern']):
            return 'Junior'
        elif any(term in all_titles for term in ['manager', 'supervisor']):
            return 'Manager'
        else:
            # Infer from total experience
            total_experience = sum(role.duration_years for role in roles)
            if total_experience >= 8:
                return 'Senior'
            elif total_experience >= 3:
                return 'Mid-level'
            else:
                return 'Junior'
    
    def _compute_recent_years(self, roles: List[RoleExperience], window_years: int = 5) -> float:
        """Compute years of experience within the recent time window."""
        if not roles:
            return 0.0
        
        current_year = datetime.now().year
        cutoff_year = current_year - window_years
        recent_years = 0.0
        
        for role in roles:
            if role.start_year is None:
                # If we don't have start year, assume the entire role is recent if it's short
                if role.duration_years <= window_years:
                    recent_years += role.duration_years
                continue
            
            # Calculate overlap with recent window
            role_end = role.end_year or current_year
            role_start = role.start_year
            
            overlap_start = max(role_start, cutoff_year)
            overlap_end = min(role_end, current_year)
            
            if overlap_start <= overlap_end:
                recent_years += max(0.0, overlap_end - overlap_start)
        
        return recent_years