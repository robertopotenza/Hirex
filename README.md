# Hirex

A lightweight matching platform that uses a heuristic AI engine to connect candidate profiles to job postings. The project ships with a FastAPI service and a reusable Python matching engine that can be embedded in other backends or automated workflows.

## Features

- Weighted scoring engine that considers skills, experience, salary expectations, location preferences, and industry fit.
- FastAPI service exposing a `/match` endpoint to request recommendations for multiple candidates at once.
- Configurable weights per request to emphasise specific hiring priorities.
- Comprehensive unit tests covering the core scoring logic.

## Getting Started

### 1. Install dependencies

Create a virtual environment (recommended) and install project requirements:

```bash
pip install -r requirements.txt
pip install -e .
```

### 2. Run the API locally

```bash
uvicorn app.main:app --reload
```

Once the server is running you can explore the automatically generated docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Request matches

Send a POST request to `http://localhost:8000/match` with the list of candidates and job postings you want to compare. Example payload:

```json
{
  "candidates": [
    {
      "id": "cand-1",
      "full_name": "Alex Dev",
      "years_experience": 5,
      "skills": ["Python", "FastAPI", "SQL"],
      "desired_salary": 90000,
      "preferred_locations": ["Berlin"],
      "open_to_remote": true,
      "industries": ["FinTech", "SaaS"]
    }
  ],
  "jobs": [
    {
      "id": "job-1",
      "title": "Backend Engineer",
      "company": "Acme Corp",
      "required_skills": ["Python", "FastAPI"],
      "nice_to_have_skills": ["SQL"],
      "minimum_years_experience": 4,
      "salary_min": 85000,
      "salary_max": 100000,
      "location": "Berlin",
      "remote_allowed": true,
      "industries": ["FinTech"]
    }
  ],
  "top_n": 3
}
```

The response returns ranked jobs per candidate, including the score breakdown for transparency.

### 4. Run tests

```bash
pytest
```

## Project Structure

```
app/               FastAPI application entrypoint
src/hirex/         Reusable matching engine package
└── engine.py      Core scoring heuristics
└── models.py      Pydantic models shared by the engine and API
tests/             Unit tests for the matching engine
```

## Extending the Engine

- Adjust the default weights in `MatchingWeights` to change how individual factors contribute to the final score.
- Replace the heuristic functions in `MatchingEngine` with embeddings or ML-based scoring if you want a more advanced AI approach.
- Persist candidates and jobs in a database and feed them into the engine to create a full recruitment platform.

## License

This project is provided as-is without warranty. Adapt it to suit your hiring workflows.
