from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class JobPosting(BaseModel):
    source: str = Field(..., description="Job source site, e.g., linkedin, indeed, glassdoor")
    external_id: str = Field(..., description="Unique ID of the job posting on the source site")
    title: str = Field(..., description="Job title")
    company: Optional[str] = Field(None, description="Company hiring")
    location: Optional[str] = Field(None, description="Job location")
    description: str = Field(..., description="Full text description of the job")
    requirements: Optional[str] = Field(None, description="Parsed/extracted requirements from description")
    job_url: str = Field(..., description="Direct link to the job application/description page")
    date_posted: Optional[date] = Field(None, description="Date when job was posted")
    salary: Optional[str] = Field(None, description="Salary info if available")

class MatchResult(BaseModel):
    score: int = Field(..., description="Match score from 0 to 100")
    justification: str = Field(..., description="One-paragraph justification of why the candidate fits or does not fit the job")
    key_matches: List[str] = Field(..., description="List of technologies, experiences, or keywords from the candidate's resume that match the job requirements")
    gaps: List[str] = Field(..., description="List of requirements in the job description that the candidate is missing")
    recommendation: str = Field(..., description="Recommendation status: 'Apply', 'Consider', or 'Skip'")

class ProcessedJob(BaseModel):
    job: JobPosting
    match: MatchResult
    processed_at: datetime = Field(default_factory=datetime.utcnow)
    input_tokens: int = Field(default=0, description="Input tokens used in Gemini call")
    output_tokens: int = Field(default=0, description="Output tokens generated in Gemini call")
    cost_usd: float = Field(default=0.0, description="Calculated API cost in USD")

