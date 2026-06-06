import time
import logging
from typing import List, Optional
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
from src.config import settings
from src.models import JobPosting, MatchResult, ProcessedJob
from src.utils.resume_parser import extract_resume_text
from src.utils.prompts import EVALUATION_PROMPT
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class JobEvaluator:
    def __init__(self, resume_path: str, api_key: str):
        """Initializes the evaluator, configures Gemini API and extracts the resume text."""
        self.resume_path = resume_path
        self.api_key = api_key
        genai.configure(api_key=self.api_key)
        
        # Load resume text once to reuse across evaluations
        self.resume_text = extract_resume_text(self.resume_path)
        logger.info("Resume text successfully loaded into Evaluator Agent.")
        
        # Use gemini-2.5-flash for fast, structured evaluations
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _call_gemini_api(self, prompt: str) -> GenerateContentResponse:
        """Helper to invoke Gemini API with retries for rate limits/transient errors."""
        return self.model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=MatchResult,  # Enforce schema constraint directly on Gemini
                temperature=0.2,
            )
        )

    def evaluate_job(self, job: JobPosting) -> Optional[ProcessedJob]:
        """
        Evaluates a single job posting against the loaded resume using Gemini.
        Returns a ProcessedJob object if successful, None otherwise.
        """
        logger.info(f"Evaluating job: {job.title} at {job.company}...")
        
        prompt = EVALUATION_PROMPT.format(
            resume_text=self.resume_text,
            job_title=job.title,
            company=job.company or "Não informada",
            job_location=job.location or "Não informado",
            description=job.description
        )

        try:
            start_time = time.time()
            response = self._call_gemini_api(prompt)
            duration = time.time() - start_time
            logger.debug(f"Gemini API call took {duration:.2f} seconds.")
            
            # Parse the response text as MatchResult
            response_text = response.text.strip()
            match_result = MatchResult.model_validate_json(response_text)
            
            # Extract usage metadata
            input_tokens = 0
            output_tokens = 0
            cost_usd = 0.0
            
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count
                # Gemini 2.5 Flash pricing: Input = $0.075 / 1M tokens, Output = $0.30 / 1M tokens
                cost_usd = (input_tokens * 0.075 / 1_000_000) + (output_tokens * 0.30 / 1_000_000)
                
            logger.info(
                f"Evaluation complete. Score: {match_result.score}/100 | "
                f"Cost: ${cost_usd:.6f} ({input_tokens} prompt, {output_tokens} completion)"
            )
            
            return ProcessedJob(
                job=job,
                match=match_result,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd
            )
        except Exception as e:
            logger.error(f"Failed to evaluate job {job.title} ({job.external_id}): {e}", exc_info=True)
            return None

    def evaluate_batch(self, jobs: List[JobPosting], delay_seconds: float = 2.0) -> List[ProcessedJob]:
        """
        Evaluates a list of jobs, respecting API rate limits (delay between calls).
        """
        processed_jobs = []
        total = len(jobs)
        logger.info(f"Starting evaluation of {total} jobs...")

        for idx, job in enumerate(jobs, 1):
            logger.info(f"[{idx}/{total}] Processing job evaluation...")
            processed = self.evaluate_job(job)
            if processed:
                processed_jobs.append(processed)
            
            # Rate limiting delay for free tier accounts
            if idx < total:
                logger.debug(f"Waiting {delay_seconds}s for rate limits...")
                time.sleep(delay_seconds)

        logger.info(f"Batch evaluation complete. Successfully evaluated {len(processed_jobs)} out of {total} jobs.")
        return processed_jobs
