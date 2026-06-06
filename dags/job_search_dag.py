import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.decorators import task

logger = logging.getLogger(__name__)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2026, 6, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="job_search_agent_pipeline",
    default_args=default_args,
    description="Multi-agent automated pipeline for collecting, scoring and notifying job postings.",
    schedule_interval="0 12 * * *",  # Everyday at 12:00 PM (noon)
    catchup=False,
    max_active_runs=1,
) as dag:

    @task
    def init_database_task():
        """Task 1: Initializes the PostgreSQL database tables."""
        from src.database import init_db
        logger.info("Initializing database...")
        init_db()
        return True

    @task
    def extract_keywords_task():
        """Task 2: Extracts keyword search terms from resume using Gemini."""
        from src.config import settings
        from src.utils.resume_parser import get_resume_keywords
        
        logger.info(f"Analyzing resume at {settings.RESUME_PATH} to extract keywords...")
        keywords = get_resume_keywords(settings.RESUME_PATH, settings.GEMINI_API_KEY)
        logger.info(f"Keywords extracted: {keywords}")
        return keywords

    @task
    def collect_jobs_task(keywords: list[str]):
        """Task 3: Uses JobSpy to scrape job listings for all extracted keywords."""
        from src.config import settings
        from src.agents.collector import collect_jobs
        
        logger.info("Starting collection of new job listings...")
        jobs = collect_jobs(
            search_terms=keywords,
            location=settings.SEARCH_LOCATION,
            country=settings.SEARCH_COUNTRY,
            results_wanted=settings.RESULTS_PER_SEARCH
        )
        # Serialize list of Pydantic models to dicts for XCom storage
        serialized_jobs = [job.model_dump() for job in jobs]
        logger.info(f"Collected {len(serialized_jobs)} raw jobs.")
        return serialized_jobs

    @task
    def filter_duplicates_task(serialized_jobs: list[dict]):
        """Task 4: Filters out jobs that already exist in the database."""
        from src.database import job_exists
        from src.models import JobPosting
        
        logger.info("Filtering duplicate job postings...")
        unique_jobs = []
        for job_dict in serialized_jobs:
            job = JobPosting(**job_dict)
            if not job_exists(job.source, job.external_id):
                unique_jobs.append(job_dict)
                
        logger.info(f"Filtered {len(serialized_jobs) - len(unique_jobs)} duplicates. {len(unique_jobs)} new jobs to evaluate.")
        return unique_jobs

    @task
    def evaluate_jobs_task(unique_serialized_jobs: list[dict]):
        """Task 5: Evaluates new jobs using Gemini against the resume text."""
        from src.config import settings
        from src.models import JobPosting
        from src.agents.evaluator import JobEvaluator
        
        if not unique_serialized_jobs:
            logger.info("No new jobs to evaluate.")
            return []
            
        evaluator = JobEvaluator(settings.RESUME_PATH, settings.GEMINI_API_KEY)
        
        jobs_to_evaluate = [JobPosting(**job_dict) for job_dict in unique_serialized_jobs]
        
        # Free tier has a 15 RPM limit, 2-3s delay is good
        processed_jobs = evaluator.evaluate_batch(jobs_to_evaluate, delay_seconds=2.0)
        
        serialized_processed = [p_job.model_dump(mode="json") for p_job in processed_jobs]
        return serialized_processed

    @task
    def save_results_task(serialized_processed_jobs: list[dict]):
        """Task 6: Persists the evaluation results to the database."""
        from src.database import save_job
        from src.models import ProcessedJob
        
        if not serialized_processed_jobs:
            logger.info("No evaluations to save.")
            return False
            
        logger.info(f"Saving {len(serialized_processed_jobs)} evaluations to DB...")
        saved_count = 0
        for p_job_dict in serialized_processed_jobs:
            processed_job = ProcessedJob(**p_job_dict)
            if save_job(processed_job):
                saved_count += 1
                
        logger.info(f"Saved {saved_count} job evaluations to DB.")
        return True

    @task
    def send_notifications_task(db_saved: bool):
        """Task 7: Notifies user via email of all high-scoring unnotified jobs."""
        from src.config import settings
        from src.database import get_unnotified_high_score_jobs, mark_as_notified
        from src.agents.notifier import send_jobs_notification
        
        logger.info(f"Searching for unnotified jobs with score >= {settings.MIN_MATCH_SCORE}...")
        high_match_jobs = get_unnotified_high_score_jobs(settings.MIN_MATCH_SCORE)
        
        if not high_match_jobs:
            logger.info("No new high-match job opportunities to notify.")
            return False
            
        # Send notifications
        success = send_jobs_notification(high_match_jobs, settings.MIN_MATCH_SCORE)
        
        if success:
            # Mark these specific jobs as notified
            job_ids = [(p_job.job.source, p_job.job.external_id) for p_job in high_match_jobs]
            mark_as_notified(job_ids)
            logger.info(f"Successfully notified user about {len(high_match_jobs)} jobs.")
            return True
        else:
            logger.error("Failed to send notification email.")
            return False

    # Pipeline task dependencies
    db_init = init_database_task()
    keywords = extract_keywords_task()
    raw_jobs = collect_jobs_task(keywords)
    unique_jobs = filter_duplicates_task(raw_jobs)
    evaluated = evaluate_jobs_task(unique_jobs)
    saved = save_results_task(evaluated)
    notified = send_notifications_task(saved)

    # Database initialization happens before collection
    db_init >> raw_jobs
