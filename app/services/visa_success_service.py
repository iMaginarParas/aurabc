import json
import logging
from .openai_service import ReplicateOpenAIMock
from typing import Dict, Any, List

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize Replicate mock client
openai_client = None
if settings.openai_api_key:
    try:
        if settings.openai_api_key.startswith("sk-"):
            import openai
            openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info("Official OpenAI client initialized successfully in Visa Success Service.")
        else:
            openai_client = ReplicateOpenAIMock(api_key=settings.openai_api_key)
            logger.info("Replicate client proxy initialized successfully in Visa Success Service.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client in Visa Success: {str(e)}")


def evaluate_visa_readiness_ai(
    country: str,
    academic: int,
    financial: int,
    document: int,
    travel: int,
    interview: int
) -> Dict[str, Any]:
    """
    Evaluates student's visa application metrics against country immigration gates using OpenAI.
    """
    system_prompt = """You are an expert immigration officer, risk evaluation algorithm, and student visa consultant.
Evaluate the student's readiness scores (each out of 100) and target country. Return a JSON object with these exact fields:
- "overall_score": integer (calculated average score weighted by country criteria).
- "risk_level": string ("Low", "Medium", or "High").
- "critical_issues": array of strings (minimum 2 key risks or gaps).
- "suggested_improvements": array of strings (actionable steps to raise score).
- "estimated_approval_confidence": integer (confidence percentage).
"""

    prompt = f"""Target Study Country: {country}
READINESS CATEGORY SCORES (out of 100):
- Academic Preparedness: {academic}
- Financial Soundness: {financial}
- Document Verifications: {document}
- Travel/Bio readiness: {travel}
- Interview confidence: {interview}
"""

    if openai_client:
        try:
            logger.info("Evaluating Visa Readiness via OpenAI ChatGPT API.")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if content:
                return json.loads(content.strip())
        except Exception as e:
            logger.error(f"OpenAI Visa Readiness evaluation failed: {str(e)}. Using fallback engine.")

    # Rule-based Fallback
    avg_score = int((academic + financial + document + travel + interview) / 5)
    risk = "High" if avg_score < 60 else "Medium" if avg_score < 80 else "Low"
    
    critical = []
    improvements = []
    if financial < 75:
        critical.append("Funding balance is below the recommended safety buffer range.")
        improvements.append("Increase education loan limit or show verified liquid sponsor assets.")
    if document < 80:
        critical.append("Incomplete document checklist items flagged (e.g. medical clearance or certified transcripts).")
        improvements.append("Complete certified translations and biometrics pre-booking files.")
        
    if not critical:
        critical.append("No immediate critical bottlenecks detected.")
        improvements.append("Conduct a final checklist audit 2 days before submission.")

    return {
        "overall_score": avg_score,
        "risk_level": risk,
        "critical_issues": critical,
        "suggested_improvements": improvements,
        "estimated_approval_confidence": int(avg_score * 0.95)
    }


def analyze_visa_interview_answer_ai(
    country: str,
    question: str,
    student_answer: str
) -> Dict[str, Any]:
    """
    Submits a student's practice visa interview answer to ChatGPT for critiques, confidence checks, and grading scores.
    """
    system_prompt = f"""You are an expert visa officer conducting interviews for {country} student visa approval checks.
Evaluate the student's answer to the visa question. Inspect for key refusal risks: lack of family ties, insufficient finance knowledge, or vague study goals.
Return a JSON object containing:
- "feedback": string (critique of answer strength).
- "score": integer (out of 100).
- "rating": string ("Excellent", "Good", "Needs Improvement", or "Critical Risk").
- "suggestions": string (actionable improvements or wording changes).
"""

    prompt = f"""Target Country: {country}
Visa Question: {question}
Student's Answer: {student_answer}
"""

    if openai_client:
        try:
            logger.info("Analyzing Visa Interview practice response via OpenAI.")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if content:
                return json.loads(content.strip())
        except Exception as e:
            logger.error(f"OpenAI Visa Interview feedback failed: {str(e)}. Using fallback engine.")

    # Fallback critique
    word_count = len(student_answer.split())
    if word_count < 15:
        return {
            "feedback": "Your answer is too short. Visa officers look for complete, confident explanations.",
            "score": 45,
            "rating": "Needs Improvement",
            "suggestions": "Elaborate with specific details. Name the modules of your course and state your exact post-study returns plan."
        }
    
    return {
        "feedback": "Answer has solid structure, but could emphasize home country return ties more clearly.",
        "score": 78,
        "rating": "Good",
        "suggestions": "Explicitly mention your long-term career aspirations in your home country after graduating."
    }
