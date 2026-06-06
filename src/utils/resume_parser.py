import os
import json
import logging
import fitz  # PyMuPDF
import google.generativeai as genai
from typing import List

logger = logging.getLogger(__name__)

_resume_text_cache = None

def extract_resume_text(pdf_path: str) -> str:
    """
    Extracts plain text from a PDF resume file.
    Caches results in memory to avoid repetitive disk reads.
    """
    global _resume_text_cache
    if _resume_text_cache is not None:
        return _resume_text_cache

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found at path: {pdf_path}")

    logger.info(f"Extracting text from resume: {pdf_path}")
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        logger.error(f"Error reading PDF file: {e}")
        raise

    _resume_text_cache = text.strip()
    return _resume_text_cache

def get_resume_keywords(pdf_path: str, api_key: str) -> List[str]:
    """
    Extracts 3-5 core search terms (job titles or technologies) from the resume
    using Gemini, to be used by the Collector Agent.
    Caches keywords to a local json file to avoid duplicate API calls.
    """
    cache_path = os.path.join(os.path.dirname(pdf_path), "keywords_cache.json")
    
    # Try reading cache first
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_keywords = json.load(f)
                if cached_keywords and isinstance(cached_keywords, list):
                    logger.info(f"Using cached keywords: {cached_keywords}")
                    return cached_keywords
        except Exception as e:
            logger.warning(f"Failed to read keywords cache: {e}")

    # Extract text from resume
    resume_text = extract_resume_text(pdf_path)
    
    logger.info("Extracting job search keywords from resume using Gemini...")
    genai.configure(api_key=api_key)
    # Using gemini-2.5-flash as it's the current fast and reliable model for general tasks
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""
    You are an expert tech recruiter and ATS optimizer.
    Analyze the following candidate's resume and extract 3 to 5 specific, high-yield job search terms or phrases (in English) 
    that would be used to search for open job postings matching this candidate on LinkedIn, Indeed, and Glassdoor.
    
    Guidelines:
    - Keep terms concise (e.g., "Python Developer", "Backend Engineer", "Data Engineer", "Machine Learning Engineer").
    - Do not use overly generic single words unless highly relevant.
    - Return ONLY a JSON list of strings, like: ["Term 1", "Term 2", "Term 3"]
    - Do NOT include markdown code blocks, formatting, or extra text. Return raw JSON.

    Resume:
    {resume_text}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            )
        )
        keywords = json.loads(response.text.strip())
        if not isinstance(keywords, list):
            raise ValueError("LLM response is not a list")
        
        # Cache the result
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(keywords, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Extracted and cached keywords: {keywords}")
        return keywords
    except Exception as e:
        logger.error(f"Error extracting keywords using Gemini: {e}")
        # Default fallback keywords
        fallback = ["Software Engineer", "Backend Developer", "Python Developer"]
        logger.info(f"Using fallback keywords: {fallback}")
        return fallback
