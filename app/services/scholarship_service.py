import json
import logging
import openai
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Scholarship

logger = logging.getLogger(__name__)

openai_client = None
if settings.openai_api_key:
    try:
        if settings.openai_api_key.startswith("sk-"):
            openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info("Official OpenAI client initialized successfully in Scholarship Service.")
        else:
            from .openai_service import ReplicateOpenAIMock
            openai_client = ReplicateOpenAIMock(api_key=settings.openai_api_key)
            logger.info("Replicate client proxy initialized successfully in Scholarship Service.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client in Scholarship Matcher: {str(e)}")


def evaluate_scholarship_matches_ai(
    db: Session,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Submits student qualifications and catalog entries to OpenAI to generate matched recommendations.
    """
    # Load scholarships catalog
    db_scholars = db.query(Scholarship).all()
    scholar_list = []
    for s in db_scholars:
        scholar_list.append({
            "name": s.name,
            "provider": s.provider,
            "country": s.country,
            "university": s.university,
            "funding_amount": s.funding_amount,
            "coverage": s.coverage,
            "eligibility_criteria": s.eligibility_criteria,
            "difficulty_level": s.difficulty_level,
            "deadline": s.deadline,
            "website": s.website_placeholder
        })

    system_prompt = """You are a senior global academic advisor, university scholarship evaluator, and financial aid counselor.
Match the student's academic and financial profile against the provided scholarships catalog.
Return a ranked list of matches.

JSON RESPONSE SCHEMA SPECIFICATION:
Your response must be a single JSON object. Output ONLY raw JSON, do NOT wrap it in markdown code blocks.
The JSON must contain a single root field "matches", which is a list of objects. Each object must have these exact fields:
- "scholarship_name": string.
- "provider": string.
- "country": string.
- "university": string (if specific, or "All Universities").
- "funding_amount": string.
- "coverage": string.
- "eligibility_criteria": string.
- "required_documents": string (comma-separated list of required files).
- "deadline": string.
- "website": string.
- "ai_match_percentage": integer (1 to 100).
- "difficulty_level": string ("High", "Medium", "Low").
- "application_strategy": string (actionable steps to apply).
- "reason_for_recommendation": string (explanation of suitability).
"""

    prompt = f"""STUDENT PROFILE:
{json.dumps(profile, indent=2)}

AVAILABLE SCHOLARSHIPS CATALOG:
{json.dumps(scholar_list, indent=2)}
"""

    if openai_client:
        try:
            logger.info("Matching Scholarships via OpenAI ChatGPT API.")
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
                res_json = json.loads(content.strip())
                return res_json.get("matches", [])
        except Exception as e:
            logger.error(f"OpenAI Scholarship matching failed: {str(e)}. Resolving local fallback.")

    return get_fallback_scholarship_matches(scholar_list, profile)


def get_fallback_scholarship_matches(
    catalog: List[Dict[str, Any]],
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Local heuristic fallback matching catalog parser.
    """
    logger.info("Compiling local fallback scholarship recommendations.")
    preferred_countries = [c.lower().strip() for c in profile.get("preferred_countries", [])]
    gpa = profile.get("gpa_percentage", 80.0)

    matches = []
    filtered_catalog = catalog
    if preferred_countries:
        filtered_catalog = [s for s in catalog if s["country"].lower().strip() in preferred_countries]

    if not filtered_catalog:
        filtered_catalog = catalog

    for idx, s in enumerate(filtered_catalog):
        base_match = 85 - (idx * 5)
        # Factor GPA limits
        if gpa < 80.0 and s["difficulty_level"] == "High":
            base_match -= 20
        elif gpa > 90.0:
            base_match += 5

        base_match = max(40, min(99, base_match))

        matches.append({
            "scholarship_name": s["name"],
            "provider": s["provider"],
            "country": s["country"],
            "university": s.get("university") or "All Universities",
            "funding_amount": s["funding_amount"],
            "coverage": s["coverage"],
            "eligibility_criteria": s["eligibility_criteria"],
            "required_documents": "Academic transcripts, Statement of Purpose, Two Letters of Recommendation",
            "deadline": s.get("deadline") or "2026-06-30",
            "website": s.get("website") or "https://auraroutes.com/scholarships",
            "ai_match_percentage": base_match,
            "difficulty_level": s["difficulty_level"],
            "application_strategy": "Draft an outstanding Statement of Purpose highlighting your GPA and academic accomplishments early.",
            "reason_for_recommendation": f"Strong compatibility based on your GPA of {gpa}% and preferred country {s['country']}."
        })

    matches.sort(key=lambda x: x["ai_match_percentage"], reverse=True)
    return matches


def evaluate_funding_planner_ai(
    profile: Dict[str, Any],
    planner: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Submits total budgets, savings, and loan limits to ChatGPT to generate a suggested payment plan and advice.
    """
    system_prompt = """You are a student financial aid officer and study abroad budget planner.
Generate a structured suggested plan and advice based on the student's costs and available funds.
Return a JSON object containing:
- "suggested_plan": string (multi-paragraph payment strategy description).
- "financial_readiness_score": integer (out of 100).
- "recommendations": array of strings (actionable financial safety tips).
"""

    prompt = f"""STUDENT BUDGET TARGETS:
{json.dumps(planner, indent=2)}
"""

    if openai_client:
        try:
            logger.info("Generating AI Funding roadmap advice.")
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
            logger.error(f"OpenAI Funding plan evaluator failed: {str(e)}. Using fallback engine.")

    # Fallback plan
    total = planner["total_cost"]
    avail = planner["total_available"]
    gap = planner["funding_gap"]
    score = 100 if total == 0 else min(100, max(10, int((avail / total) * 100)))

    recs = [
        "Apply for merit-based university fee waivers as primary target.",
        "Secure additional educational loan buffers before visa filing limits check."
    ]
    if gap > 0:
        plan_desc = f"You have a calculated funding deficit gap of ₹{gap:,.2f}. We suggest raising your educational loan limits or adding co-signers with fixed asset collateral."
    else:
        plan_desc = "Your current funding available matches or exceeds estimated tuition and living bounds. Maintain liquid balances in check blocks."

    return {
        "suggested_plan": plan_desc,
        "financial_readiness_score": score,
        "recommendations": recs
    }
