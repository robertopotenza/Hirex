"""Integration tests for the FastAPI endpoints."""

from __future__ import annotations

try:  # pragma: no cover - fallback used only when httpx is unavailable
    import httpx  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    import json as json_module
    import sys
    from types import ModuleType
    from typing import Any, Iterable, Mapping, Sequence
    from urllib.parse import urlencode, urljoin, urlsplit

    class _Headers:
        def __init__(self, headers: Any | None = None) -> None:
            self._items: list[tuple[str, str]] = []
            if headers is None:
                return
            if isinstance(headers, _Headers):
                self._items.extend(headers.multi_items())
            elif isinstance(headers, Mapping):
                for key, value in headers.items():
                    if isinstance(value, (list, tuple)):
                        for item in value:
                            self._items.append((str(key), str(item)))
                    else:
                        self._items.append((str(key), str(value)))
            else:
                for key, value in headers:
                    self._items.append((str(key), str(value)))

        def get(self, key: str, default: str | None = None) -> str | None:
            key_lower = key.lower()
            for name, value in reversed(self._items):
                if name.lower() == key_lower:
                    return value
            return default

        def multi_items(self) -> list[tuple[str, str]]:
            return list(self._items)

        def __contains__(self, key: str) -> bool:
            return self.get(key) is not None

    class _URL:
        def __init__(self, url: str) -> None:
            self._url = url
            parsed = urlsplit(url)
            self.scheme = parsed.scheme or "http"
            path = parsed.path or "/"
            self.path = path
            self.raw_path = path.encode("ascii", errors="ignore")
            self.netloc = parsed.netloc.encode("ascii", errors="ignore")
            self.query = parsed.query.encode("ascii", errors="ignore")

        def __str__(self) -> str:
            return self._url

    class _Request:
        def __init__(
            self,
            method: str,
            url: str,
            headers: Any | None = None,
            content: bytes | None = None,
        ) -> None:
            self.method = method.upper()
            self.url = _URL(url)
            self.headers = _Headers(headers)
            self._content = content or b""

        def read(self) -> bytes:
            return self._content

    class _ByteStream:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self) -> bytes:
            return self._data

    class _Response:
        def __init__(
            self,
            status_code: int,
            headers: Iterable[tuple[str, str]] | None = None,
            stream: _ByteStream | None = None,
            request: _Request | None = None,
        ) -> None:
            self.status_code = status_code
            self.headers = _Headers(headers or [])
            self._stream = stream or _ByteStream(b"")
            self.request = request
            self._content: bytes | None = None

        def read(self) -> bytes:
            if self._content is None:
                self._content = self._stream.read()
            return self._content

        @property
        def content(self) -> bytes:
            return self.read()

        @property
        def text(self) -> str:
            data = self.content
            return data.decode("utf-8") if data else ""

        def json(self) -> Any:
            data = self.content
            if not data:
                return None
            return json_module.loads(data.decode("utf-8"))

    class _BaseTransport:
        def handle_request(self, request: _Request) -> _Response:  # pragma: no cover
            raise NotImplementedError

    class _UseClientDefault:
        pass

    USE_CLIENT_DEFAULT = _UseClientDefault()

    class _Client:
        def __init__(
            self,
            *,
            app: Any | None = None,
            base_url: str = "http://testserver",
            headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
            transport: _BaseTransport | None = None,
            follow_redirects: bool = True,
            cookies: Any = None,
        ) -> None:
            if not base_url.endswith("/"):
                base_url += "/"
            self.base_url = base_url
            self._transport = transport
            self._base_headers = _Headers(headers or {})
            self.follow_redirects = follow_redirects
            self.cookies = cookies
            self.app = app

        def _merge_url(self, url: str | bytes) -> str:
            if isinstance(url, bytes):
                url = url.decode("utf-8")
            return urljoin(self.base_url, str(url))

        def request(
            self,
            method: str,
            url: str,
            *,
            content: bytes | str | None = None,
            data: Mapping[str, Any] | Sequence[tuple[str, Any]] | bytes | None = None,
            files: Any = None,
            json: Any = None,
            params: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
            headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
            cookies: Any = None,
            auth: Any = None,
            follow_redirects: Any = None,
            allow_redirects: Any = None,
            timeout: Any = None,
            extensions: Any = None,
        ) -> _Response:
            if self._transport is None:
                raise RuntimeError("No transport configured for httpx stub client.")

            target_url = self._merge_url(url)
            if params:
                query_string = urlencode(params, doseq=True)
                separator = "&" if "?" in target_url else "?"
                target_url = f"{target_url}{separator}{query_string}"

            header_pairs = list(self._base_headers.multi_items())
            if headers:
                header_pairs.extend(_Headers(headers).multi_items())

            body: bytes
            if json is not None:
                body = json_module.dumps(json).encode("utf-8")
                if not any(name.lower() == "content-type" for name, _ in header_pairs):
                    header_pairs.append(("content-type", "application/json"))
            elif content is not None:
                body = content.encode("utf-8") if isinstance(content, str) else content
            elif data is not None:
                if isinstance(data, (bytes, bytearray)):
                    body = bytes(data)
                else:
                    body = urlencode(data, doseq=True).encode("utf-8")
                    header_pairs.append(("content-type", "application/x-www-form-urlencoded"))
            else:
                body = b""

            request = _Request(method, target_url, headers=header_pairs, content=body)
            response = self._transport.handle_request(request)
            return response

        def get(self, url: str, **kwargs: Any) -> _Response:
            return self.request("GET", url, **kwargs)

        def post(self, url: str, **kwargs: Any) -> _Response:
            return self.request("POST", url, **kwargs)

        def put(self, url: str, **kwargs: Any) -> _Response:
            return self.request("PUT", url, **kwargs)

        def delete(self, url: str, **kwargs: Any) -> _Response:
            return self.request("DELETE", url, **kwargs)

        def options(self, url: str, **kwargs: Any) -> _Response:
            return self.request("OPTIONS", url, **kwargs)

        def head(self, url: str, **kwargs: Any) -> _Response:
            return self.request("HEAD", url, **kwargs)

        def patch(self, url: str, **kwargs: Any) -> _Response:
            return self.request("PATCH", url, **kwargs)

        def close(self) -> None:
            return None

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            self.close()

    httpx = ModuleType("httpx")
    httpx.BaseTransport = _BaseTransport
    httpx.Request = _Request
    httpx.Response = _Response
    httpx.Client = _Client
    httpx.ByteStream = _ByteStream
    httpx.Headers = _Headers
    httpx.USE_CLIENT_DEFAULT = USE_CLIENT_DEFAULT
    httpx._client = ModuleType("httpx._client")
    httpx._client.USE_CLIENT_DEFAULT = USE_CLIENT_DEFAULT
    httpx._client.UseClientDefault = _UseClientDefault
    httpx._types = ModuleType("httpx._types")
    httpx._types.URLTypes = str
    httpx._types.RequestContent = object
    httpx._types.RequestFiles = object
    httpx._types.QueryParamTypes = object
    httpx._types.HeaderTypes = object
    httpx._types.CookieTypes = object
    httpx._types.AuthTypes = object
    httpx._types.TimeoutTypes = object

    sys.modules["httpx"] = httpx
    sys.modules["httpx._client"] = httpx._client
    sys.modules["httpx._types"] = httpx._types

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from hirex.engine import MatchingEngine
from hirex.models import CandidateProfile, JobPosting, MatchingWeights

client = TestClient(app)


def _candidate_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "candidate-123",
        "full_name": "Jamie Candidate",
        "years_experience": 6,
        "skills": ["Python", "FastAPI", "SQL"],
        "desired_salary": 95000,
        "preferred_locations": ["Berlin"],
        "open_to_remote": True,
        "industries": ["SaaS", "FinTech"],
    }
    data.update(overrides)
    return data


def _job_payload(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "job-456",
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "required_skills": ["Python", "FastAPI"],
        "nice_to_have_skills": ["SQL"],
        "minimum_years_experience": 4,
        "salary_min": 85000,
        "salary_max": 110000,
        "location": "Berlin",
        "remote_allowed": True,
        "industries": ["SaaS"],
    }
    data.update(overrides)
    return data


def test_health_endpoint_reports_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint_returns_html_interface() -> None:
    response = client.get("/")

    assert response.status_code == 200
    content_type = response.headers.get("content-type", "")
    assert "text/html" in content_type
    
    # Check that the HTML contains expected content
    html_content = response.text
    assert "Hirex" in html_content
    assert "Intelligent Job Matching API" in html_content
    assert "v0.1.0" in html_content
    assert "API Documentation" in html_content
    assert "Health Check" in html_content
    assert "Key Features" in html_content


def test_match_endpoint_returns_matching_engine_results() -> None:
    candidate_payload = _candidate_payload()
    job_payload = _job_payload()

    response = client.post(
        "/match",
        json={"candidates": [candidate_payload], "jobs": [job_payload], "top_n": 1},
    )

    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {"weights", "results"}
    assert len(body["results"]) == 1

    candidate_model = CandidateProfile(**candidate_payload)
    job_model = JobPosting(**job_payload)
    engine = MatchingEngine()
    expected_match = engine.match_candidates_to_jobs(
        [candidate_model], [job_model], top_n=1
    )[0].matches[0]

    assert body["weights"] == engine.weights.model_dump()

    result = body["results"][0]
    assert result["candidate"]["id"] == candidate_payload["id"]
    assert len(result["matches"]) == 1

    match_json = result["matches"][0]
    assert match_json["job"]["id"] == job_payload["id"]
    assert match_json["score"] == expected_match.score
    assert match_json["breakdown"]["skills"] == pytest.approx(
        expected_match.breakdown.skills
    )
    assert match_json["breakdown"]["experience"] == pytest.approx(
        expected_match.breakdown.experience
    )
    assert match_json["breakdown"]["salary"] == pytest.approx(
        expected_match.breakdown.salary
    )
    assert match_json["breakdown"]["location"] == pytest.approx(
        expected_match.breakdown.location
    )
    assert match_json["breakdown"]["industry"] == pytest.approx(
        expected_match.breakdown.industry
    )


def test_match_endpoint_applies_custom_weights() -> None:
    candidate_payload = _candidate_payload(desired_salary=150000)
    job_payload = _job_payload(salary_max=100000)
    custom_weights_payload = {
        "skills": 0.2,
        "experience": 0.1,
        "salary": 0.5,
        "location": 0.1,
        "industry": 0.1,
    }

    response = client.post(
        "/match",
        json={
            "candidates": [candidate_payload],
            "jobs": [job_payload],
            "weights": custom_weights_payload,
            "top_n": 1,
        },
    )

    assert response.status_code == 200

    body = response.json()
    assert body["weights"] == MatchingWeights(**custom_weights_payload).model_dump()
    assert len(body["results"]) == 1

    candidate_model = CandidateProfile(**candidate_payload)
    job_model = JobPosting(**job_payload)
    custom_weights = MatchingWeights(**custom_weights_payload)
    custom_engine = MatchingEngine(custom_weights)
    expected_custom_match = custom_engine.match_candidates_to_jobs(
        [candidate_model], [job_model], top_n=1
    )[0].matches[0]

    default_engine = MatchingEngine()
    default_score = default_engine.match_candidates_to_jobs(
        [candidate_model], [job_model], top_n=1
    )[0].matches[0].score

    result = body["results"][0]
    assert result["candidate"]["id"] == candidate_payload["id"]
    assert len(result["matches"]) == 1

    match_json = result["matches"][0]
    assert match_json["job"]["id"] == job_payload["id"]
    assert match_json["score"] == expected_custom_match.score
    assert match_json["score"] < default_score
    assert match_json["breakdown"]["salary"] == pytest.approx(
        expected_custom_match.breakdown.salary
    )
    assert match_json["breakdown"]["skills"] == pytest.approx(
        expected_custom_match.breakdown.skills
    )
    assert match_json["breakdown"]["experience"] == pytest.approx(
        expected_custom_match.breakdown.experience
    )
    assert match_json["breakdown"]["location"] == pytest.approx(
        expected_custom_match.breakdown.location
    )
    assert match_json["breakdown"]["industry"] == pytest.approx(
        expected_custom_match.breakdown.industry
    )
