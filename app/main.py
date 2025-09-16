"""FastAPI application exposing the Hirex matching engine."""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from hirex.engine import MatchingEngine
from hirex.models import CandidateMatches, CandidateProfile, JobPosting, MatchingWeights
from hirex.resume_parser import ResumeParser
from hirex.job_scraper import LinkedInJobScraper

app = FastAPI(
    title="Hirex Matching API",
    description=(
        "Suggest job matches for a collection of candidate profiles using "
        "weighted heuristic scoring."
    ),
    version="0.1.0",
)

# Setup templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

_default_engine = MatchingEngine()
_resume_parser = ResumeParser()
_job_scraper = LinkedInJobScraper()


class MatchRequest(BaseModel):
    candidates: List[CandidateProfile] = Field(..., description="Profiles to evaluate")
    jobs: List[JobPosting] = Field(..., description="Job postings available for matching")
    top_n: int = Field(3, ge=1, le=20, description="Maximum number of matches per candidate")
    weights: Optional[MatchingWeights] = Field(
        default=None, description="Override the default scoring weights"
    )


class MatchResponse(BaseModel):
    weights: MatchingWeights
    results: List[CandidateMatches]


@app.get("/", response_class=HTMLResponse, summary="API interface")
async def root(request: Request) -> HTMLResponse:
    context = {
        "name": "Hirex Matching API",
        "version": "0.1.0",
        "description": "Suggest job matches for candidate profiles using weighted heuristic scoring",
        "docs": "/docs",
        "health": "/health"
    }
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return {"message": "No favicon available for this API"}


@app.get("/health", summary="Service health probe")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/match", response_model=MatchResponse, summary="Match candidates to jobs")
async def match(request: MatchRequest) -> MatchResponse:
    if request.weights is not None:
        engine = MatchingEngine(request.weights)
    else:
        engine = _default_engine

    results = engine.match_candidates_to_jobs(
        request.candidates, request.jobs, top_n=request.top_n
    )
    return MatchResponse(weights=engine.weights, results=results)


@app.get("/matcher", response_class=HTMLResponse, summary="Job matching interface")
async def matcher_ui(request: Request) -> HTMLResponse:
    """Serve the LinkedIn job matching user interface."""
    return templates.TemplateResponse(request, "matcher.html", {})


@app.get("/skills-dashboard", response_class=HTMLResponse, summary="Skills analysis dashboard")
async def skills_dashboard(request: Request) -> HTMLResponse:
    """Serve the skills analysis dashboard interface."""
    return templates.TemplateResponse(request, "skills.html", {})


@app.post("/analyze-jobs", response_model=MatchResponse, summary="Analyze LinkedIn jobs against resume")
async def analyze_jobs(
    resume: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    job_urls: str = Form(..., description="LinkedIn job URLs, one per line")
) -> MatchResponse:
    """
    Analyze compatibility between uploaded resume and LinkedIn job postings.
    
    - **resume**: PDF or DOCX file containing candidate's resume
    - **job_urls**: LinkedIn job posting URLs, separated by newlines
    """
    try:
        # Validate file type
        if not resume.filename.lower().endswith(('.pdf', '.docx')):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file type. Please upload a PDF or DOCX file."
            )
        
        # Read resume file
        resume_content = await resume.read()
        
        # Parse resume to extract candidate profile
        try:
            candidate = _resume_parser.parse_resume(resume_content, resume.filename)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse resume: {str(e)}"
            )
        
        # Parse and validate job URLs
        urls = [url.strip() for url in job_urls.strip().split('\n') if url.strip()]
        if not urls:
            raise HTTPException(
                status_code=400,
                detail="Please provide at least one LinkedIn job URL."
            )
        
        # Scrape job postings
        jobs = []
        failed_urls = []
        
        for url in urls:
            try:
                job = _job_scraper.scrape_job_posting(url)
                jobs.append(job)
            except Exception as e:
                failed_urls.append(f"{url}: {str(e)}")
        
        if not jobs:
            error_details = "\n".join(failed_urls) if failed_urls else "No valid job postings found"
            raise HTTPException(
                status_code=400,
                detail=f"Failed to scrape job postings:\n{error_details}"
            )
        
        # Perform matching
        results = _default_engine.match_candidates_to_jobs(
            [candidate], jobs, top_n=len(jobs)
        )
        
        response = MatchResponse(weights=_default_engine.weights, results=results)
        
        # Add warning about failed URLs if any
        if failed_urls:
            # In a production app, you might want to log these or include them in the response
            pass
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
