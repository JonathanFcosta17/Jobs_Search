import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from src.config import settings
from src.models import ProcessedJob
from jinja2 import Template

logger = logging.getLogger(__name__)

# Premium HTML email template with custom CSS styling and badges
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>New Job Postings — AI Matcher</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f5f7;
            color: #333333;
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }
        .container {
            max-width: 650px;
            margin: 20px auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #e1e4e8;
        }
        .header {
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            color: #ffffff;
            padding: 30px 24px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }
        .header p {
            margin: 8px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }
        .content {
            padding: 24px;
        }
        .summary {
            font-size: 15px;
            color: #4b5563;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #e5e7eb;
        }
        .job-card {
            background-color: #fafafa;
            border-left: 4px solid #3b82f6;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
            border-top: 1px solid #f0f0f0;
            border-right: 1px solid #f0f0f0;
            border-bottom: 1px solid #f0f0f0;
        }
        .job-card.high-match {
            border-left-color: #10b981;
        }
        .job-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }
        .job-title {
            font-size: 18px;
            font-weight: 700;
            margin: 0;
            color: #111827;
        }
        .job-company {
            font-size: 14px;
            color: #4b5563;
            margin: 4px 0 0 0;
            font-weight: 500;
        }
        .score-badge {
            background-color: #e0f2fe;
            color: #0369a1;
            font-size: 14px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 9999px;
            display: inline-block;
        }
        .score-badge.high-match {
            background-color: #d1fae5;
            color: #065f46;
        }
        .meta-info {
            font-size: 12px;
            color: #9ca3af;
            margin-bottom: 14px;
        }
        .meta-item {
            margin-right: 16px;
            display: inline-block;
        }
        .justification {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 12px 16px;
            font-size: 14px;
            color: #374151;
            margin-bottom: 14px;
            font-style: italic;
        }
        .details-list {
            margin: 0 0 16px 0;
            padding-left: 20px;
            font-size: 13px;
        }
        .details-list li {
            margin-bottom: 4px;
        }
        .matches-list {
            color: #059669;
        }
        .gaps-list {
            color: #d97706;
        }
        .btn-apply {
            display: inline-block;
            background-color: #2563eb;
            color: #ffffff !important;
            text-decoration: none;
            padding: 8px 18px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            text-align: center;
            transition: background-color 0.2s;
        }
        .btn-apply:hover {
            background-color: #1d4ed8;
        }
        .footer {
            background-color: #f3f4f6;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #9ca3af;
            border-top: 1px solid #e5e7eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💼 Jobs Search AI Agent</h1>
            <p>Your autonomous job search assistant</p>
        </div>
        <div class="content">
            <div class="summary">
                Hello,<br><br>
                New job postings matching your profile have been found and evaluated.<br>
                Below are the <strong>{{ jobs|length }} best opportunities</strong> that reached your minimum match score of <strong>{{ min_score }}</strong>.
                <br><br>
                <div style="font-size: 13px; color: #6b7280; border-top: 1px dashed #e5e7eb; padding-top: 10px; line-height: 1.8;">
                    📊 <strong>LLMOps Usage Audit:</strong><br>
                    Estimated Run Cost: <strong>${{ "%.4f"|format(total_cost) }}</strong> | 
                    Total Tokens: <strong>{{ total_input_tokens + total_output_tokens }}</strong> 
                    ({{ total_input_tokens }} prompt, {{ total_output_tokens }} completion)
                </div>
            </div>
            
            {% for p_job in jobs %}
            <div class="job-card {{ 'high-match' if p_job.match.score >= 85 else '' }}">
                <div class="job-header">
                    <div>
                        <h2 class="job-title">{{ p_job.job.title }}</h2>
                        <p class="job-company">{{ p_job.job.company }} — {{ p_job.job.location }}</p>
                    </div>
                    <div>
                        <span class="score-badge {{ 'high-match' if p_job.match.score >= 85 else '' }}">
                            Score: {{ p_job.match.score }}
                        </span>
                    </div>
                </div>
                
                <div class="meta-info">
                    <span class="meta-item">Platform: <strong>{{ p_job.job.source.upper() }}</strong></span>
                    {% if p_job.job.salary %}
                    <span class="meta-item">Salary: <strong>{{ p_job.job.salary }}</strong></span>
                    {% endif %}
                </div>
                
                <div class="justification">
                    <strong>AI Evaluation:</strong> {{ p_job.match.justification }}
                </div>
                
                {% if p_job.match.key_matches %}
                <div style="font-size: 13px; font-weight: 600; color: #065f46; margin-bottom: 4px;">✅ Key Matches / Strengths:</div>
                <ul class="details-list matches-list">
                    {% for item in p_job.match.key_matches %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
                
                {% if p_job.match.gaps %}
                <div style="font-size: 13px; font-weight: 600; color: #9a3412; margin-bottom: 4px;">⚠️ Missing Requirements / Gaps:</div>
                <ul class="details-list gaps-list">
                    {% for item in p_job.match.gaps %}
                    <li>{{ item }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
                
                <div style="margin-top: 15px;">
                    <a href="{{ p_job.job.job_url }}" class="btn-apply" target="_blank">View Job / Apply</a>
                </div>
            </div>
            {% endfor %}
        </div>
        <div class="footer">
            This report was automatically generated by the Jobs Search AI Agent.<br>
            Next search scheduled via Apache Airflow.
        </div>
    </div>
</body>
</html>
"""

def send_jobs_notification(jobs: List[ProcessedJob], min_score: int) -> bool:
    """
    Renders the jobs report into HTML and sends it via SMTP (Gmail).
    """
    if not jobs:
        logger.info("No high-match jobs to send in notification.")
        return False
        
    logger.info(f"Sending email notification with {len(jobs)} jobs to {settings.NOTIFICATION_EMAIL}...")
    
    # Calculate usage aggregates for LLMOps reporting
    total_input_tokens = sum(getattr(j, "input_tokens", 0) or 0 for j in jobs)
    total_output_tokens = sum(getattr(j, "output_tokens", 0) or 0 for j in jobs)
    total_cost = sum(getattr(j, "cost_usd", 0.0) or 0.0 for j in jobs)
    
    # Render template using Jinja2
    template = Template(EMAIL_TEMPLATE)
    html_content = template.render(
        jobs=jobs,
        min_score=min_score,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_cost=total_cost
    )
    
    # Create MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 AI Job Alerts — {len(jobs)} New Matching Jobs"
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = settings.NOTIFICATION_EMAIL
    
    msg.attach(MIMEText(html_content, "html"))
    
    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.SMTP_EMAIL, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_EMAIL, settings.NOTIFICATION_EMAIL, msg.as_string())
        logger.info(
            f"Notification email sent successfully. "
            f"Usage metrics: {total_input_tokens + total_output_tokens} tokens spent, total cost: ${total_cost:.6f}"
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}", exc_info=True)
        return False
