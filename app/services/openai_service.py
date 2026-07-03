import json
import logging
from openai import OpenAI
from ..config import settings
from ..prompts.eligibility_prompts import SYSTEM_PROMPT, format_eligibility_prompt
from ..schemas import AIResultEvaluation

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None
if settings.openai_api_key:
    client = OpenAI(api_key=settings.openai_api_key)
else:
    logger.warning("OPENAI_API_KEY is not configured in settings. Fallback mock values will be used.")

def evaluate_student_profile(profile_dict: dict) -> AIResultEvaluation:
    """
    Sends the student profile details to the OpenAI API and returns a structured evaluation.
    Falls back to a deterministic heuristic validation if OpenAI is not set up, times out, or fails.
    """
    user_prompt = format_eligibility_prompt(profile_dict)
    
    if client:
        try:
            logger.info("Calling OpenAI API for student profile evaluation...")
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Highly cost-effective and supports structured JSON format
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                timeout=12.0  # Set an upper limit on waiting time to prevent hanging
            )
            
            content = response.choices[0].message.content
            logger.info("OpenAI response received successfully.")
            
            # Parse response
            raw_evaluation = json.loads(content)
            
            # Validate response via Pydantic model
            return AIResultEvaluation(**raw_evaluation)
            
        except Exception as e:
            logger.error(f"OpenAI API call or parsing failed: {str(e)}. Executing local heuristic fallback...")
    
    # HEURISTIC FALLBACK EVALUATION ENGINE
    # This evaluates the profile algorithmically if the AI fails or API key is absent.
    logger.info("Running deterministic heuristic profile evaluation...")
    
    gpa10 = profile_dict.get("gpa_10th", 7.0)
    gpa12 = profile_dict.get("gpa_12th", 7.0)
    ielts = profile_dict.get("english_score") or 6.0
    backlogs = 0 # Assume 0
    work_exp = profile_dict.get("work_experience", 0.0)
    gap_years = profile_dict.get("gap_years", 0)
    pref_country = profile_dict.get("preferred_country", "Canada")
    pref_course = profile_dict.get("preferred_course", "Data Science")

    # Base heuristic scoring logic
    base_score = int(((gpa10 + gpa12) / 2) * 8) # e.g. GPA 8.5 -> 68
    if ielts >= 7.0:
        base_score += 15
    elif ielts >= 6.5:
        base_score += 10
    else:
        base_score += 5
        
    if work_exp > 0:
        base_score += min(10, int(work_exp * 3))
        
    base_score -= min(15, gap_years * 5)
    
    overall_score = max(35, min(98, base_score))
    
    # Determinations
    prob = "High" if overall_score >= 75 else "Medium" if overall_score >= 55 else "Low"
    schol = "High" if overall_score >= 82 else "Medium" if overall_score >= 65 else "Low"
    visa = "High" if overall_score >= 70 else "Medium" if overall_score >= 50 else "Low"

    # Match country config
    rec_countries = [pref_country]
    if pref_country != "Germany" and overall_score >= 80:
        rec_countries.append("Germany")
    if pref_country != "UK":
        rec_countries.append("United Kingdom")

    # Match universities
    rec_univs = []
    if "canada" in pref_country.lower():
        rec_univs = [
            {"name": "University of Toronto", "location": "Canada", "reasoning": "Top-tier CS choice aligned with your strong profile."},
            {"name": "York University", "location": "Canada", "reasoning": "Excellent co-op programs matching your budget guidelines."}
        ]
    elif "uk" in pref_country.lower() or "united kingdom" in pref_country.lower():
        rec_univs = [
            {"name": "University of Manchester", "location": "UK", "reasoning": "Prestige research hub aligned with your graduation records."},
            {"name": "Coventry University", "location": "UK", "reasoning": "Flexible intake options fitting your graduation year."}
        ]
    else:
        rec_univs = [
            {"name": "Trinity College Dublin", "location": "Ireland", "reasoning": "English-speaking EU tech hub matching your study course."},
            {"name": "Technical University of Munich", "location": "Germany", "reasoning": "Zero tuition fees ideal for minimizing educational expenses."}
        ]

    # Strengths/Weaknesses
    strengths = ["Solid 10th and 12th foundation records"]
    if ielts >= 6.5:
        strengths.append(f"Strong English verification score ({ielts} IELTS)")
    if work_exp > 0:
        strengths.append(f"Relevant professional experience ({work_exp} yrs)")
    if profile_dict.get("passport_available"):
        strengths.append("Active passport available for immediate filing")

    weaknesses = []
    if gap_years > 0:
        weaknesses.append(f"Identified {gap_years} study gap years")
    if ielts < 6.5:
        weaknesses.append("English score is below competitive margins")

    improvements = ["Schedule IELTS recheck or target PTE to increase average scores"]
    if gap_years > 0:
        improvements.append("Compile internships and professional courses to substantiate gap years")
    improvements.append("Draft custom SOP focusing on career transitions and future goals")

    next_steps = [
        "Get your academic transcripts apostilled",
        "Book a detailed expert consultation to shortlist final 3 universities",
        "Initiate education loan pre-approval procedures"
    ]

    return AIResultEvaluation(
        overall_score=overall_score,
        admission_probability=prob,
        scholarship_potential=schol,
        visa_readiness=visa,
        strengths=strengths,
        weaknesses=weaknesses,
        suggested_improvements=improvements,
        recommended_countries=rec_countries,
        recommended_universities=rec_univs,
        suggested_next_steps=next_steps
    )
