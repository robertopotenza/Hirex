"""Setup configuration for the Hirex package."""

from setuptools import find_packages, setup

setup(
    name="hirex",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "fastapi==0.110.0",
        "uvicorn==0.29.0",
        "pydantic==2.6.4",
    ],
    python_requires=">=3.8",
    author="Hirex Team",
    description="Job matching engine for candidates and job postings",
)