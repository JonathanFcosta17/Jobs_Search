import pytest
from unittest.mock import MagicMock, patch
from src.utils.resume_parser import extract_resume_text

@patch("src.utils.resume_parser.fitz.open")
def test_extract_resume_text_success(mock_fitz_open):
    # Mocking fitz PDF structures
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Candidate experience: Python Developer."
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc
    
    # We force reset of global cache inside resume_parser
    import src.utils.resume_parser
    src.utils.resume_parser._resume_text_cache = None

    text = extract_resume_text("dummy_resume.pdf")
    
    assert text == "Candidate experience: Python Developer."
    mock_fitz_open.assert_called_once_with("dummy_resume.pdf")
    mock_doc.close.assert_called_once()
