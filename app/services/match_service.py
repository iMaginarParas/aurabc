import json
import logging
import openai
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from ..config import settings
from ..models import University

logger = logging.getLogger(__name__)

# Initialize OpenAI
openai_client = None
if settings.openai_api_key:
    try:
        openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized successfully in Match Service.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client in Matcher: {str(e)}")

def evaluate_university_matches_ai(
    db: Session,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Queries OpenAI to match and rank top universities from our catalog
    against the student's academic achievements and preferences.
    """
    # 1. Fetch catalog universities to inject into prompt context
    db_unis = db.query(University).all()
    uni_list = []
    for u in db_unis:
        uni_list.append({
            "name": u.name,
            "country": u.country,
            "world_ranking": u.world_ranking,
            "tuition_fee_range": u.tuition_fee_range,
            "average_living_cost": u.average_living_cost,
            "admission_rate": u.admission_rate
        })

    system_prompt = """You are an expert global education consultant, university matching algorithm, and visa risk advisor.
Your task is to analyze the student's academic profile and preferences against the provided catalog of top global universities, and generate a ranked list of 10-20 recommendations.

JSON RESPONSE SCHEMA SPECIFICATION:
Your response must be a single JSON object. Do NOT wrap the JSON inside markdown code blocks (e.g. ```json). Output only the raw JSON.
The JSON must contain a single root field "recommendations", which is a list of objects. Each object must have these exact fields:
- "match_percentage": integer (1 to 100) representing fit.
- "university_name": string (name from the catalog).
- "country": string.
- "course": string (specific course matched to student's interest).
- "tuition_fee": string.
- "living_cost": string.
- "scholarship_opportunities": string (eligibility and funding details).
- "admission_requirements": string (GPA, english thresholds, standard requirements).
- "visa_difficulty": string (one of: Low, Medium, High, with brief reasoning).
- "employment_opportunities": string (post-study work visa rights and jobs).
- "ai_recommendation_summary": string (reasoning detailing why this is a match).
"""

    prompt = f"""STUDENT ACADEMIC & FINANCIAL PROFILE:
{json.dumps(profile, indent=2)}

AVAILABLE CATALOG OF TOP UNIVERSITIES:
{json.dumps(uni_list, indent=2)}
"""

    if openai_client:
        try:
            logger.info(f"Querying OpenAI for University Matcher recommendations.")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if content:
                res_json = json.loads(content.strip())
                return res_json.get("recommendations", [])
        except Exception as e:
            logger.error(f"OpenAI university match failed: {str(e)}. Resolving local fallback.")

    return get_fallback_university_matches(uni_list, profile)


def get_fallback_university_matches(unis: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Local heuristic fallback engine when OpenAI is not responding.
    Ranks, filters, and formats catalog matches.
    """
    logger.info("Compiling local university matching recommendations.")
    
    preferred_countries = [c.lower().strip() for c in profile.get("preferred_countries", [])]
    target_course = profile.get("course", "Computer Science")
    gpa = profile.get("gpa_percentage", 80.0)

    recommendations = []
    
    # Filter by country if preferences are specified
    filtered_unis = unis
    if preferred_countries:
        filtered_unis = [u for u in unis if u["country"].lower().strip() in preferred_countries]
    
    # If no country matches filter, return all catalog entries to ensure results exist
    if not filtered_unis:
        filtered_unis = unis

    # Rank and calculate score heuristics
    for idx, u in enumerate(filtered_unis):
        # Calculate base match score
        match_score = 95 - (idx * 3)
        # Factor GPA limits
        if gpa < 75.0 and u.get("world_ranking", 100) < 10:
            match_score -= 15
        elif gpa > 90.0 and u.get("world_ranking", 100) < 20:
            match_score += 3
            
        match_score = max(50, min(99, match_score))

        recommendations.append({
            "match_percentage": match_score,
            "university_name": u["name"],
            "country": u["country"],
            "course": f"{profile.get('degree_level', 'M.S.')} in {target_course}",
            "tuition_fee": u["tuition_fee_range"],
            "living_cost": u["average_living_cost"],
            "scholarship_opportunities": "Up to 25% tuition fee waiver based on academic performance." if profile.get("scholarship_required") else "Merit-based university scholarships available.",
            "admission_requirements": f"Minimum GPA: {u.get('admission_rate', '70%')} equivalent. English test: IELTS 6.5+ or equivalent.",
            "visa_difficulty": "Low" if u["country"] in ["Germany", "Ireland"] else "Medium",
            "employment_opportunities": f"2-3 years post-study work visa rights in {u['country']}.",
            "ai_recommendation_summary": f"Strong suitability match based on your GPA of {gpa}% and preferences. {u['name']} offers stellar outcomes for {target_course}."
        })

    # Sort by match percentage descending
    recommendations.sort(key=lambda x: x["match_percentage"], reverse=True)
    return recommendations
