# Reusable Prompt Templates for AI Eligibility Evaluation

SYSTEM_PROMPT = """
You are a highly experienced global study abroad admissions director, visa officer, and academic planning coordinator.
Your task is to review a student's profile details and generate a highly detailed, trustworthy, and actionable study abroad eligibility evaluation report.

You MUST respond with a strict, valid JSON object matching the JSON schema below.
DO NOT include any commentary, extra notes, markdown wrappers (like ```json), or whitespace around the JSON object. Just return the raw JSON object.

JSON SCHEMA:
{
  "overall_score": 85, // integer between 0 and 100 based on GPA, English score, and experience
  "admission_probability": "High", // "Low", "Medium", or "High"
  "scholarship_potential": "Medium", // "Low", "Medium", or "High"
  "visa_readiness": "High", // "Low", "Medium", or "High"
  "strengths": ["Strong GPA in Bachelors", "No backlogs", "Has active passport"], // list of strings
  "weaknesses": ["English score slightly below top-tier average", "Has 2 gap years"], // list of strings
  "suggested_improvements": ["Retake IELTS to aim for 7.5+", "Add a professional internship to cover gap years"], // list of strings
  "recommended_countries": ["Canada", "United Kingdom"], // list of strings
  "recommended_universities": [
    {
      "name": "University of Toronto",
      "location": "Canada",
      "reasoning": "Strong match for your GPA and budget, offers excellent post-study work paths."
    }
  ],
  "suggested_next_steps": ["Compile financial proof documents", "Prepare reference letters", "Schedule expert consultation call"] // list of strings
}
"""

USER_PROMPT_TEMPLATE = """
Evaluate the following study abroad profile:

=== PERSONAL DETAILS ===
Name: {full_name}
Nationality: {nationality}
Resident Country: {country_residence}

=== ACADEMIC TRANSCRIPTS ===
Highest Qualification: {qualification}
10th Grade Score: {gpa_10th}
12th Grade Score: {gpa_12th}
Bachelor's CGPA: {cgpa_bachelors}
Master's CGPA: {cgpa_masters}
Graduation Year: {grad_year}

=== LANGUAGE CREDENTIALS ===
English Proficiency Exam: {english_exam}
Exam Score: {english_score}

=== STUDY PREFERENCES ===
Target Country: {preferred_country}
Target Major/Course: {preferred_course}
Target Intake: {preferred_intake}
Tuition & Living Budget: {budget_range}
Scholarship Required: {scholarship_required}

=== ADDITIONAL STATS ===
Work Experience: {work_experience} years
Gap Years: {gap_years} years
NEET Score: {neet_score} (only relevant if target course is MBBS)
Active Passport Available: {passport_available}
"""

def format_eligibility_prompt(profile: dict) -> str:
    """
    Formats the user evaluation prompt using the student's profile details.
    """
    return USER_PROMPT_TEMPLATE.format(
        full_name=profile.get("full_name"),
        nationality=profile.get("nationality"),
        country_residence=profile.get("country_residence"),
        qualification=profile.get("qualification"),
        gpa_10th=profile.get("gpa_10th"),
        gpa_12th=profile.get("gpa_12th"),
        cgpa_bachelors=profile.get("cgpa_bachelors") if profile.get("cgpa_bachelors") is not None else "N/A",
        cgpa_masters=profile.get("cgpa_masters") if profile.get("cgpa_masters") is not None else "N/A",
        grad_year=profile.get("grad_year"),
        english_exam=profile.get("english_exam"),
        english_score=profile.get("english_score") if profile.get("english_score") is not None else "Not Taken",
        preferred_country=profile.get("preferred_country"),
        preferred_course=profile.get("preferred_course"),
        preferred_intake=profile.get("preferred_intake"),
        budget_range=profile.get("budget_range"),
        scholarship_required="Yes" if profile.get("scholarship_required") else "No",
        work_experience=profile.get("work_experience", 0),
        gap_years=profile.get("gap_years", 0),
        neet_score=profile.get("neet_score") if profile.get("neet_score") is not None else "N/A",
        passport_available="Yes" if profile.get("passport_available") else "No"
    )
