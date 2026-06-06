import pytest
from unittest.mock import MagicMock, patch
from src.database import job_exists, save_job
from src.models import JobPosting, MatchResult, ProcessedJob
from datetime import datetime, date

@pytest.fixture
def mock_db_connection():
    with patch("src.database.get_db_connection") as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        yield mock_cursor

def test_job_exists_true(mock_db_connection):
    # Setup cursor mock response
    mock_db_connection.fetchone.return_value = (1,)
    
    exists = job_exists("linkedin", "12345")
    
    assert exists is True
    # Verify execute was called with correct parameters
    mock_db_connection.execute.assert_called_once()
    query = mock_db_connection.execute.call_args[0][0]
    params = mock_db_connection.execute.call_args[0][1]
    assert "SELECT 1 FROM jobs" in query
    assert params == ("linkedin", "12345")

def test_job_exists_false(mock_db_connection):
    mock_db_connection.fetchone.return_value = None
    
    exists = job_exists("indeed", "67890")
    
    assert exists is False

def test_save_job_success(mock_db_connection):
    job = JobPosting(
        source="linkedin",
        external_id="12345",
        title="Software Engineer",
        company="Tech Corp",
        location="Remote",
        description="Write code in Python.",
        job_url="http://example.com/job",
        date_posted=date(2026, 6, 1)
    )
    match = MatchResult(
        score=85,
        justification="Great profile matching Python experience.",
        key_matches=["Python"],
        gaps=[],
        recommendation="Apply"
    )
    processed_job = ProcessedJob(job=job, match=match, processed_at=datetime(2026, 6, 1, 12, 0, 0))
    
    success = save_job(processed_job)
    
    assert success is True
    mock_db_connection.execute.assert_called_once()
    query = mock_db_connection.execute.call_args[0][0]
    assert "INSERT INTO jobs" in query
