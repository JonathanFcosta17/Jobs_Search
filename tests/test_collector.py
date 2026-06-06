import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from src.agents.collector import collect_jobs

@patch("src.agents.collector.scrape_jobs")
def test_collect_jobs_success(mock_scrape_jobs):
    # Mock return pandas DataFrame from JobSpy
    mock_df = pd.DataFrame([
        {
            "id": "job_111",
            "site": "linkedin",
            "title": "Data Scientist",
            "company": "DataCorp",
            "location": "Boston, MA",
            "description": "Must know machine learning and Python.",
            "job_url": "http://linkedin.com/jobs/111",
            "date_posted": "2026-06-01",
            "salary": "$120,000/yr"
        },
        {
            "id": "job_222",
            "site": "indeed",
            "title": "Machine Learning Engineer",
            "company": "AI Labs",
            "location": "Remote",
            "description": "Building neural networks.",
            "job_url": "http://indeed.com/jobs/222",
            "date_posted": None,
            "salary": None
        }
    ])
    mock_scrape_jobs.return_value = mock_df

    # Execute collector
    jobs = collect_jobs(search_terms=["ML Engineer"], location="Remote", country="USA", results_wanted=2)

    assert len(jobs) == 2
    
    # First job verification
    assert jobs[0].external_id == "job_111"
    assert jobs[0].source == "linkedin"
    assert jobs[0].title == "Data Scientist"
    assert jobs[0].company == "DataCorp"
    assert jobs[0].salary == "$120,000/yr"
    
    # Second job verification
    assert jobs[1].external_id == "job_222"
    assert jobs[1].source == "indeed"
    assert jobs[1].salary is None
    
    mock_scrape_jobs.assert_called_once()
