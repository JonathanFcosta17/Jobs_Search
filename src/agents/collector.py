import logging
import pandas as pd
from datetime import datetime, date
from typing import List
from jobspy import scrape_jobs
from src.models import JobPosting
from src.config import settings

logger = logging.getLogger(__name__)

def _safe_date(val) -> date | None:
    """Helper to convert various date formats from JobSpy safely."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    try:
        # Try converting string
        return datetime.strptime(str(val), "%Y-%m-%d").date()
    except Exception:
        return None

def _safe_str(val) -> str:
    """Helper to safely convert values to string, returning empty string on null."""
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()

def collect_jobs(search_terms: List[str], location: str, country: str = "USA", results_wanted: int = 15) -> List[JobPosting]:
    """
    Leverages python-jobspy to fetch job openings from LinkedIn, Indeed, and Glassdoor.
    Runs searches for multiple keywords and consolidates them into a standardized list of JobPosting.
    """
    all_postings = []
    seen_urls = set()

    sites = ["linkedin", "indeed", "glassdoor"]
    
    logger.info(f"Starting job collection for terms: {search_terms} in {location} ({country})")

    for term in search_terms:
        logger.info(f"Searching for term: '{term}'...")
        try:
            # We scrape jobs for LinkedIn, Indeed, and Glassdoor.
            # Some sites might throw errors due to anti-bot measures. We catch them to not crash the process.
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location,
                results_wanted=results_wanted,
                country_indeed=country.lower(),
                linkedin_fetch_description=True  # Important to get full description for evaluation
            )
            
            if df is None or df.empty:
                logger.warning(f"No results found for term '{term}'.")
                continue
                
            logger.info(f"Found {len(df)} raw results for term '{term}'.")
            
            # Map DataFrame rows to JobPosting models
            for _, row in df.iterrows():
                url = _safe_str(row.get("job_url"))
                if not url or url in seen_urls:
                    continue
                
                # Extract external ID. Often JobSpy provides a unique ID or we can extract it from the URL.
                ext_id = _safe_str(row.get("id"))
                if not ext_id:
                    # Fallback to hashing URL or using URL end if ID is missing
                    ext_id = str(hash(url))

                # Normalize source name
                source = _safe_str(row.get("site", "unknown")).lower()
                
                # Check description length/presence
                desc = _safe_str(row.get("description"))
                if not desc:
                    # Skip jobs without descriptions as they can't be evaluated by the LLM
                    logger.debug(f"Skipping job {ext_id} due to empty description.")
                    continue

                posting = JobPosting(
                    source=source,
                    external_id=ext_id,
                    title=_safe_str(row.get("title", "Untitled")),
                    company=_safe_str(row.get("company", "Unknown")),
                    location=_safe_str(row.get("location", location)),
                    description=desc,
                    requirements=None,  # Will be extracted or analyzed by the LLM
                    job_url=url,
                    date_posted=_safe_date(row.get("date_posted")),
                    salary=_safe_str(row.get("salary")) or None
                )
                
                all_postings.append(posting)
                seen_urls.add(url)
                
        except Exception as e:
            logger.error(f"Error scraping jobs for term '{term}': {e}", exc_info=True)
            continue
            
    logger.info(f"Total unique jobs collected: {len(all_postings)}")
    return all_postings
