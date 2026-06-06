import json
import logging
from contextlib import contextmanager
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from src.config import settings
from src.models import JobPosting, MatchResult, ProcessedJob

logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection():
    db_url = settings.DATABASE_URL
    try:
        conn = psycopg2.connect(db_url)
    except psycopg2.OperationalError as e:
        # Fallback to localhost if host is 'postgres' and connection fails (running outside Docker)
        if "@postgres:" in db_url:
            local_db_url = db_url.replace("@postgres:", "@localhost:")
            try:
                conn = psycopg2.connect(local_db_url)
            except Exception:
                raise e
        else:
            raise
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """Initializes the database schema if it doesn't exist and runs dynamic migrations."""
    query = """
    CREATE TABLE IF NOT EXISTS jobs (
        id SERIAL PRIMARY KEY,
        external_id VARCHAR(255) NOT NULL,
        source VARCHAR(50) NOT NULL,
        title VARCHAR(500) NOT NULL,
        company VARCHAR(255),
        location VARCHAR(255),
        description TEXT,
        job_url VARCHAR(1000) UNIQUE NOT NULL,
        date_posted DATE,
        salary VARCHAR(255),
        match_score INTEGER,
        justification TEXT,
        key_matches JSONB,
        gaps JSONB,
        recommendation VARCHAR(50),
        notified BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT NOW(),
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cost_usd NUMERIC(10, 6) DEFAULT 0.000000,
        UNIQUE(source, external_id)
    );
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            # Run ALTER TABLE commands to dynamically migrate existing database instances smoothly
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS input_tokens INTEGER DEFAULT 0;")
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS output_tokens INTEGER DEFAULT 0;")
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10, 6) DEFAULT 0.000000;")
        conn.commit()
    logger.info("Database initialized and migrated successfully.")

def job_exists(source: str, external_id: str) -> bool:
    """Checks if a job posting with given source and external ID already exists in DB."""
    query = "SELECT 1 FROM jobs WHERE source = %s AND external_id = %s LIMIT 1;"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (source, external_id))
            return cur.fetchone() is not None

def save_job(processed_job: ProcessedJob) -> bool:
    """Saves a processed job to the database."""
    query = """
    INSERT INTO jobs (
        external_id, source, title, company, location, description, job_url, date_posted, salary,
        match_score, justification, key_matches, gaps, recommendation, notified, created_at,
        input_tokens, output_tokens, cost_usd
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source, external_id) DO UPDATE SET
        match_score = EXCLUDED.match_score,
        justification = EXCLUDED.justification,
        key_matches = EXCLUDED.key_matches,
        gaps = EXCLUDED.gaps,
        recommendation = EXCLUDED.recommendation,
        created_at = EXCLUDED.created_at,
        input_tokens = EXCLUDED.input_tokens,
        output_tokens = EXCLUDED.output_tokens,
        cost_usd = EXCLUDED.cost_usd
    """
    job = processed_job.job
    match = processed_job.match
    
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    job.external_id,
                    job.source,
                    job.title,
                    job.company,
                    job.location,
                    job.description,
                    job.job_url,
                    job.date_posted,
                    job.salary,
                    match.score,
                    match.justification,
                    json.dumps(match.key_matches),
                    json.dumps(match.gaps),
                    match.recommendation,
                    False,  # notified starts as False
                    processed_job.processed_at,
                    processed_job.input_tokens,
                    processed_job.output_tokens,
                    processed_job.cost_usd
                )
            )
        conn.commit()
    return True

def get_unnotified_high_score_jobs(min_score: int) -> list[ProcessedJob]:
    """Retrieves all jobs with a match score higher or equal to min_score that haven't been notified yet."""
    query = """
    SELECT 
        external_id, source, title, company, location, description, job_url, date_posted, salary,
        match_score, justification, key_matches, gaps, recommendation, created_at,
        input_tokens, output_tokens, cost_usd
    FROM jobs
    WHERE match_score >= %s AND notified = FALSE
    ORDER BY match_score DESC;
    """
    processed_jobs = []
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, (min_score,))
            rows = cur.fetchall()
            for row in rows:
                job_posting = JobPosting(
                    source=row['source'],
                    external_id=row['external_id'],
                    title=row['title'],
                    company=row['company'],
                    location=row['location'],
                    description=row['description'],
                    job_url=row['job_url'],
                    date_posted=row['date_posted'],
                    salary=row['salary']
                )
                match_result = MatchResult(
                    score=row['match_score'],
                    justification=row['justification'],
                    key_matches=row['key_matches'] if isinstance(row['key_matches'], list) else json.loads(row['key_matches'] or "[]"),
                    gaps=row['gaps'] if isinstance(row['gaps'], list) else json.loads(row['gaps'] or "[]"),
                    recommendation=row['recommendation']
                )
                processed_jobs.append(
                    ProcessedJob(
                        job=job_posting,
                        match=match_result,
                        processed_at=row['created_at'],
                        input_tokens=row.get('input_tokens', 0) or 0,
                        output_tokens=row.get('output_tokens', 0) or 0,
                        cost_usd=float(row.get('cost_usd', 0.0) or 0.0)
                    )
                )
    return processed_jobs

def mark_as_notified(job_ids: list[tuple[str, str]]):
    """Marks specified jobs as notified in the database. job_ids is a list of (source, external_id) tuples."""
    if not job_ids:
        return
    query = "UPDATE jobs SET notified = TRUE WHERE (source = %s AND external_id = %s);"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for source, external_id in job_ids:
                cur.execute(query, (source, external_id))
        conn.commit()
    logger.info(f"Marked {len(job_ids)} jobs as notified.")
