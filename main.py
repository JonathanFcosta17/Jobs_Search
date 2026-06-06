import os
import sys
import logging
from datetime import datetime

# Setup logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main_runner")

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.config import settings
from src.models import JobPosting, ProcessedJob
from src.database import init_db, job_exists, save_job, get_unnotified_high_score_jobs, mark_as_notified
from src.utils.resume_parser import get_resume_keywords
from src.agents.collector import collect_jobs
from src.agents.evaluator import JobEvaluator
from src.agents.notifier import send_jobs_notification

def run_pipeline():
    logger.info("Starting Job Search AI Agent pipeline locally...")
    
    # 1. Initialize DB
    logger.info("Initializing database schema if not present...")
    init_db()
    
    # 2. Extract keywords from CV
    resume_path = settings.RESUME_PATH
    # Fallback to local resume folder if running outside Docker
    if not os.path.exists(resume_path) and os.path.exists("./resume/curriculo.pdf"):
        resume_path = "./resume/curriculo.pdf"
        
    logger.info(f"Using resume at: {resume_path}")
    if not os.path.exists(resume_path):
        logger.error("Resume file not found! Please place your resume in 'resume/curriculo.pdf'.")
        return
        
    keywords = get_resume_keywords(resume_path, settings.GEMINI_API_KEY)
    logger.info(f"Job search keywords: {keywords}")
    
    # 3. Collect jobs
    raw_postings = collect_jobs(
        search_terms=keywords,
        location=settings.SEARCH_LOCATION,
        country=settings.SEARCH_COUNTRY,
        results_wanted=settings.RESULTS_PER_SEARCH
    )
    
    if not raw_postings:
        logger.info("No job postings found during collection.")
        return
        
    # 4. Filter duplicates
    new_jobs = []
    for job in raw_postings:
        if not job_exists(job.source, job.external_id):
            new_jobs.append(job)
            
    logger.info(f"Filtered out {len(raw_postings) - len(new_jobs)} duplicates. {len(new_jobs)} new jobs to evaluate.")
    
    if not new_jobs:
        logger.info("No new unique jobs to process.")
        return
        
    # 5. Evaluate jobs
    evaluator = JobEvaluator(resume_path, settings.GEMINI_API_KEY)
    logger.info(f"Evaluating {len(new_jobs)} jobs with Gemini (gemini-2.5-flash)...")
    
    # Run batch evaluation
    processed_jobs = evaluator.evaluate_batch(new_jobs, delay_seconds=2.0)
    
    # 6. Save results
    saved_count = 0
    for processed_job in processed_jobs:
        if save_job(processed_job):
            saved_count += 1
    logger.info(f"Saved {saved_count} evaluations to database.")
    
    # 7. Check matches and notify
    logger.info(f"Retrieving unnotified jobs with score >= {settings.MIN_MATCH_SCORE}...")
    high_match_jobs = get_unnotified_high_score_jobs(settings.MIN_MATCH_SCORE)
    
    if not high_match_jobs:
        logger.info("No new high-match job opportunities to notify.")
        return
        
    logger.info(f"Sending notifications for {len(high_match_jobs)} matching jobs...")
    success = send_jobs_notification(high_match_jobs, settings.MIN_MATCH_SCORE)
    
    if success:
        job_ids = [(p_job.job.source, p_job.job.external_id) for p_job in high_match_jobs]
        mark_as_notified(job_ids)
        logger.info("Notifications sent and database updated successfully!")
    else:
        logger.error("Failed to send notification email.")

if __name__ == "__main__":
    run_pipeline()
