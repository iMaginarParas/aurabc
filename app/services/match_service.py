import json
import logging
import openai
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from ..config import settings
from ..models import University

logger = logging.getLogger(__name__)

openai_client = None
if settings.openai_api_key:
    try:
        if settings.openai_api_key.startswith("sk-"):
            openai_client = openai.OpenAI(api_key=settings.openai_api_key)
            logger.info("Official OpenAI client initialized successfully in Match Service.")
        else:
            from .openai_service import ReplicateOpenAIMock
            openai_client = ReplicateOpenAIMock(api_key=settings.openai_api_key)
            logger.info("Replicate client proxy initialized successfully in Match Service.")
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


def evaluate_indian_college_matches_ai(
    db: Session,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Queries OpenAI to match and rank top Indian colleges from our catalog
    against the student's academic profile and preferences.
    """
    from ..models import IndianCollege

    # 1. Fetch catalog Indian colleges
    db_colleges = db.query(IndianCollege).filter(IndianCollege.status == "Active").all()
    college_list = []
    for c in db_colleges:
        college_list.append({
            "name": c.name,
            "location": c.location,
            "state": c.state,
            "city": c.city,
            "course": c.course,
            "specializations": c.specializations,
            "neet_required": c.neet_required,
            "dasa_eligible": c.dasa_eligible,
            "ciwg_eligible": c.ciwg_eligible,
            "nri_fee_structure": c.nri_fee_structure,
            "international_fee_structure": c.international_fee_structure,
            "hostel_available": c.hostel_available,
            "website": c.website
        })

    system_prompt = """You are an expert Indian higher education consultant, college matching algorithm, and NRI admissions advisor.
Your task is to analyze the student's academic profile (including course interest, budget, preferred state and city, NEET score for MBBS, and NRI / DASA / CIWG eligibility status) against the provided catalog of Indian colleges, and generate a ranked list of matches.

JSON RESPONSE SCHEMA SPECIFICATION:
Your response must be a single JSON object. Do NOT wrap the JSON inside markdown code blocks (e.g. ```json). Output only the raw JSON.
The JSON must contain a single root field "recommendations", which is a list of objects. Each object must have these exact fields:
- "match_percentage": integer (1 to 100) representing fit.
- "college_name": string (name from the catalog).
- "location": string (city, state).
- "course": string (course matched).
- "specializations": string (comma-separated specializations matched).
- "estimated_fees": string (estimated fees based on student status - NRI, CIWG, International, or domestic).
- "eligibility": string (admission criteria met, e.g. NEET score requirement, 12th marks, NRI quota).
- "hostel_available": boolean.
- "website": string.
- "ai_recommendation_summary": string (detailed matching rationale explaining why this college is a good fit).
"""

    prompt = f"""STUDENT PROFILE & PREFERENCES:
{json.dumps(profile, indent=2)}

AVAILABLE CATALOG OF INDIAN COLLEGES:
{json.dumps(college_list, indent=2)}
"""

    if openai_client:
        try:
            logger.info(f"Querying OpenAI for Indian College Matcher recommendations.")
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
            logger.error(f"OpenAI Indian college match failed: {str(e)}. Resolving local fallback.")

    return get_fallback_indian_college_matches(college_list, profile)


def get_fallback_indian_college_matches(colleges: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Local heuristic fallback engine when OpenAI is not responding.
    Ranks, filters, and formats Indian college matches.
    """
    logger.info("Compiling local Indian college matching recommendations.")
    
    target_course = profile.get("course", "").lower().strip()
    preferred_state = profile.get("preferred_state", "").lower().strip()
    preferred_city = profile.get("preferred_city", "").lower().strip()
    neet_score = profile.get("neet_score")
    dasa_eligible = profile.get("dasa_eligible", False)
    ciwg_eligible = profile.get("ciwg_eligible", False)
    nri_status = profile.get("nri_status", False)

    recommendations = []
    
    # Filter colleges by course
    filtered_colleges = []
    for c in colleges:
        # Match course name
        if target_course in c["course"].lower():
            # If MBBS, check NEET
            if "mbbs" in c["course"].lower() and c["neet_required"] and (neet_score is None or neet_score < 137):
                continue
            # If DASA or CIWG, check eligibility
            if dasa_eligible and not c["dasa_eligible"]:
                continue
            if ciwg_eligible and not c["ciwg_eligible"]:
                continue
            filtered_colleges.append(c)

    if not filtered_colleges:
        filtered_colleges = [c for c in colleges if target_course in c["course"].lower()]
    
    if not filtered_colleges:
        filtered_colleges = colleges

    # Rank and calculate score heuristics
    for idx, c in enumerate(filtered_colleges):
        match_score = 95 - (idx * 4)
        
        # State and City matching bonus
        if preferred_state and preferred_state in c["state"].lower():
            match_score += 5
        if preferred_city and preferred_city in c["city"].lower():
            match_score += 5
            
        # NEET score bonus for MBBS
        if "mbbs" in c["course"].lower() and neet_score:
            if neet_score > 600:
                match_score += 5
            elif neet_score < 400:
                match_score -= 10
                
        match_score = max(50, min(99, match_score))

        # Determine fee display
        fees = "Domestic fees apply"
        if nri_status:
            fees = c.get("nri_fee_structure") or "NRI quota fees apply"
        elif dasa_eligible or ciwg_eligible:
            fees = c.get("nri_fee_structure") or "DASA quota fees apply"
        else:
            fees = c.get("international_fee_structure") or "International fees apply"

        recommendations.append({
            "match_percentage": match_score,
            "college_name": c["name"],
            "location": f"{c['city']}, {c['state']}",
            "course": c["course"],
            "specializations": c["specializations"] or "General",
            "estimated_fees": fees,
            "eligibility": "NEET Qualified required" if c["neet_required"] else "12th Marks merit based",
            "hostel_available": c["hostel_available"],
            "website": c["website"] or "http://education.gov.in",
            "ai_recommendation_summary": f"Strong alignment with your course choice of {c['course']}. Located in {c['city']}, {c['state']} with great infrastructure."
        })

    recommendations.sort(key=lambda x: x["match_percentage"], reverse=True)
    return recommendations


def evaluate_mbbs_abroad_matches_ai(
    db: Session,
    profile: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Queries OpenAI to match and rank top MBBS universities from our catalog
    against the student's academic profile (NEET score, budget, preferred countries, languages, etc.).
    """
    from ..models import MBBSUniversity

    # 1. Fetch catalog MBBS universities (all must be NMC approved)
    db_unis = db.query(MBBSUniversity).filter(MBBSUniversity.status == "Active", MBBSUniversity.nmc_approved == True).all()
    uni_list = []
    for u in db_unis:
        uni_list.append({
            "name": u.name,
            "country": u.country,
            "annual_fees": u.annual_fees,
            "hostel_fees": u.hostel_fees,
            "living_cost": u.living_cost,
            "duration": u.duration,
            "language": u.language,
            "eligibility": u.eligibility,
            "minimum_neet": u.minimum_neet,
            "recognition": u.recognition
        })

    system_prompt = """You are an expert global education consultant, NEET counselling advisor, and medical admissions matcher.
Your task is to analyze the student's academic profile (NEET score, category, annual budget, preferred countries, language preference, hostel / scholarship requirements, passport status) against the provided catalog of NMC-approved MBBS colleges abroad, and generate a ranked list of matched college recommendations.

JSON RESPONSE SCHEMA SPECIFICATION:
Your response must be a single JSON object. Do NOT wrap the JSON inside markdown code blocks (e.g. ```json). Output only the raw JSON.
The JSON must contain a single root field "recommendations", which is a list of objects. Each object must have these exact fields:
- "match_percentage": integer (1 to 100) representing fit.
- "university_name": string (name from the catalog).
- "country": string.
- "estimated_tuition": string (annual tuition fees).
- "living_costs": string (estimated annual living expenses).
- "scholarship_availability": string (merit-based or other funding details).
- "visa_difficulty": string (one of: Low, Medium, High, with brief reasoning).
- "career_opportunities": string (post-study licensing exam rights - NMC NEXT exam eligibility, USMLE/PLAB preparation).
- "ai_recommendation_summary": string (reasoning detailing why this is a match).
"""

    prompt = f"""STUDENT NEET & ACADEMIC PROFILE:
{json.dumps(profile, indent=2)}

AVAILABLE CATALOG OF NMC-APPROVED MBBS UNIVERSITIES:
{json.dumps(uni_list, indent=2)}
"""

    if openai_client:
        try:
            logger.info("Querying OpenAI for MBBS Abroad Matcher recommendations.")
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
            logger.error(f"OpenAI MBBS match failed: {str(e)}. Resolving local fallback.")

    return get_fallback_mbbs_matches(uni_list, profile)


def get_fallback_mbbs_matches(unis: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Local heuristic fallback engine when OpenAI is not responding.
    Ranks, filters, and formats catalog matches for MBBS.
    """
    logger.info("Compiling local MBBS matching recommendations.")
    
    preferred_countries = [c.lower().strip() for c in profile.get("preferred_countries", [])]
    neet_score = profile.get("neet_score", 0)
    category = profile.get("category", "General").lower().strip()
    language_pref = profile.get("preferred_language", "English").lower().strip()
    hostel_req = profile.get("hostel_required", True)

    # Determine NEET qualification (NMC rules: generally 137 for Gen, 107 for SC/ST/OBC in recent years)
    neet_qualifying_score = 137
    if category in ["obc", "sc", "st"]:
        neet_qualifying_score = 107
        
    is_neet_qualified = neet_score >= neet_qualifying_score

    recommendations = []
    
    # Filter by NEET score (skip universities where minimum neet is higher than candidate's score)
    filtered_unis = []
    for u in unis:
        # Check NEET eligibility
        min_neet_needed = u.get("minimum_neet") or 137
        # Adjust min neet for reserved category
        if category in ["obc", "sc", "st"] and min_neet_needed == 137:
            min_neet_needed = 107
            
        if neet_score < min_neet_needed:
            continue
            
        # Match preferred countries if specified
        if preferred_countries and u["country"].lower().strip() not in preferred_countries:
            continue
            
        filtered_unis.append(u)

    # If no country matches filter, return all qualified colleges
    if not filtered_unis:
        filtered_unis = [u for u in unis if neet_score >= (u.get("minimum_neet") or 107)]
        
    if not filtered_unis:
        filtered_unis = unis

    # Rank and calculate fit
    for idx, u in enumerate(filtered_unis):
        match_score = 90 - (idx * 3)
        
        # NEET score bonus
        if neet_score > 350:
            match_score += 8
        elif neet_score > 200:
            match_score += 4
            
        # Language preference fit
        if language_pref in u["language"].lower():
            match_score += 5
            
        match_score = max(40, min(99, match_score))

        # Career details based on country
        career = "Fully eligible for NMC NEXT exam in India, USMLE, and PLAB."
        if u["country"] == "Philippines":
            career = "Eligible for NEXT, requires NMAT check for BS-MD course structure."
        elif u["country"] == "Bangladesh":
            career = "Direct clinical familiarity with South Asian disease patterns, high NEXT success rates."

        recommendations.append({
            "match_percentage": match_score,
            "university_name": u["name"],
            "country": u["country"],
            "estimated_tuition": u["annual_fees"] + " / year",
            "living_costs": u["living_cost"],
            "scholarship_availability": "Merit scholarships available for top performers (NEET >350)." if profile.get("scholarship_required") else "No direct scholarships; fee package is already low-cost.",
            "visa_difficulty": "Low" if u["country"] in ["Georgia", "Russia", "Kazakhstan", "Egypt"] else "Medium",
            "career_opportunities": career,
            "ai_recommendation_summary": f"Great budget fit for MBBS studies in {u['country']}. Language of instruction is {u['language']}. WHO and NMC recognized."
        })

    recommendations.sort(key=lambda x: x["match_percentage"], reverse=True)
    return recommendations
