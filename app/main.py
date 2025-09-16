"""FastAPI application exposing the Hirex matching engine."""

from __future__ import annotations

from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from hirex.engine import MatchingEngine
from hirex.models import CandidateMatches, CandidateProfile, JobPosting, MatchingWeights

app = FastAPI(
    title="Hirex Matching API",
    description=(
        "Suggest job matches for a collection of candidate profiles using "
        "weighted heuristic scoring."
    ),
    version="0.1.0",
)

_default_engine = MatchingEngine()


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


@app.get("/", summary="API information")
async def root() -> dict[str, str]:
    return {
        "name": "Hirex Matching API",
        "version": "0.1.0",
        "description": "Suggest job matches for candidate profiles using weighted heuristic scoring",
        "docs": "/docs",
        "health": "/health"
    }


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
