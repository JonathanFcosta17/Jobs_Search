import pytest
from unittest.mock import MagicMock, patch
from src.agents.evaluator import JobEvaluator
from src.models import JobPosting

@patch("src.agents.evaluator.extract_resume_text")
@patch("src.agents.evaluator.genai.GenerativeModel")
def test_evaluate_job_success(mock_model_class, mock_extract):
    # Mock resume loading
    mock_extract.return_value = "Resume experience text."
    
    # Mock GenerativeModel instance and API response
    mock_model_instance = MagicMock()
    mock_response = MagicMock()
    
    # Mocked structured output from Gemini model
    mock_response.text = '{"score": 90, "justification": "Candidate has excellent skills.", "key_matches": ["Python"], "gaps": [], "recommendation": "Apply"}'
    mock_model_instance.generate_content.return_value = mock_response
    mock_model_class.return_value = mock_model_instance
    
    # Initialize evaluator (this triggers extract_resume_text)
    evaluator = JobEvaluator(resume_path="dummy.pdf", api_key="dummy_key")
    
    job = JobPosting(
        source="linkedin",
        external_id="ext_999",
        title="AI Engineer",
        company="OpenTech",
        location="Remote",
        description="Looking for AI developers fluent in Python.",
        job_url="http://example.com/ai-job"
    )
    
    processed = evaluator.evaluate_job(job)
    
    assert processed is not None
    assert processed.match.score == 90
    assert processed.match.recommendation == "Apply"
    assert processed.match.key_matches == ["Python"]
    
    mock_model_instance.generate_content.assert_called_once()
