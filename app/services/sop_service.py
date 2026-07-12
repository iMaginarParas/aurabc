from .openai_service import ReplicateOpenAIMock
import logging
from typing import Dict, Any, Optional

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize Replicate mock client
openai_client = None
if settings.openai_api_key:
    try:
        openai_client = ReplicateOpenAIMock(api_key=settings.openai_api_key)
        logger.info("Replicate client initialized successfully in SOP Service.")
    except Exception as e:
        logger.error(f"Failed to initialize Replicate client in SOP: {str(e)}")


def get_sop_system_prompt() -> str:
    """
    Returns system prompt instructing the model on tone, constraints, and structural styling rules.
    """
    return """You are a professional Statement of Purpose (SOP) writer, academic advisor, and admissions expert. 
Your goal is to write a highly compelling, personalized, and university-ready Statement of Purpose.

CRITICAL INSTRUCTIONS FOR TONE AND LANGUAGE:
- BANNED CLICHÉS: Never start with clichés like "Since childhood...", "I have always wanted to...", "From my early years...", "Fast forward to today...", or "I am writing this application because...". Start directly with a compelling intellectual hook or professional thesis.
- BANNED TRANSITIONS: Banish robotic transition words like "Furthermore", "Moreover", "In conclusion", "Additionally", "Last but not least", "It is worth mentioning". Use organic, natural paragraph transitions.
- TONE: Professional, natural, human-like, confident, academic, and clear. It must read like it was written by an ambitious and articulate human, not an AI template.
- PLAGIARISM AND ATS: Write custom, plagiarism-free sentences that bypass AI scanners by using varied sentence structures and strong active verbs.

FORMATTING SPECIFICATION:
Return the Statement of Purpose formatted in clean, simple HTML using only:
- <h2> (For major section headings, e.g., Academic Background, Motivation, Career Goals)
- <p> (For paragraph body text)
- <ul> and <li> (For bullet points, e.g., listing projects or research publications)
Do NOT include <html>, <head>, or <body> tags. Output only the body HTML content.

SOP STRUCTURE:
1. Introduction: Intellectual hook, current academic/professional focus, and core thesis.
2. Academic Journey: Key accomplishments, milestones, and relevant courses from undergraduate/postgraduate degrees.
3. Professional & Project Experience: Practical execution of skills, internships, milestones, and technical achievements.
4. Motivation & Why This Course: Clear explanations linking target course to past preparation.
5. Why This University: Specific faculty, lab, curriculum, or culture details of the target institution.
6. Why This Country: Justification for study destination.
7. Career Goals: Delineate short-term goals (immediate graduation targets) and long-term career aspirations.
8. Conclusion: Summary of applicant value proposition and closing remarks.

TARGET LENGTH: 900 to 1200 words. Keep it comprehensive and highly detailed.
"""


def generate_sop_draft(profile: Dict[str, Any]) -> str:
    """
    Sends the 6-step profile details to OpenAI to draft a premium Statement of Purpose.
    """
    p_info = profile.get("personal_info", {})
    a_info = profile.get("academic_background", {})
    w_info = profile.get("professional_experience", {})
    t_info = profile.get("target_education", {})
    g_info = profile.get("career_goals", {})
    add_info = profile.get("additional_info", {})

    prompt = f"""Write a Statement of Purpose based on the following applicant credentials:

APPLICANT PROFILE:
- Full Name: {p_info.get("full_name")}
- Nationality: {p_info.get("nationality")}
- Current Country: {p_info.get("current_country")}

ACADEMIC PROFILE:
- Highest Qualification: {a_info.get("highest_qualification")}
- University/Institution: {a_info.get("university")}
- GPA / Score: {a_info.get("cgpa_percentage")}
- Graduation Year: {a_info.get("graduation_year")}
- Academic Achievements: {a_info.get("academic_achievements", "N/A")}

PROFESSIONAL EXPERIENCE:
- Work Experience: {w_info.get("work_experience")}
- Internships: {w_info.get("internships", "N/A")}
- Projects/Skills: {w_info.get("projects", "N/A")} (Technical Skills: {w_info.get("technical_skills")})
- Certifications: {w_info.get("certifications", "N/A")}
- Research Experience: {w_info.get("research_experience", "N/A")}

TARGET ADMISSION GOAL:
- Target Country: {t_info.get("country")}
- Target University: {t_info.get("university")}
- Target Degree: {t_info.get("degree")}
- Target Course: {t_info.get("course")}
- Target Intake: {t_info.get("intake")}

CAREER & STUDY ASPIRATIONS:
- Short-Term Career Goals: {g_info.get("short_term_goals")}
- Long-Term Career Goals: {g_info.get("long_term_goals")}
- Reason for Course choice: {g_info.get("reason_course")}
- Reason for University choice: {g_info.get("reason_university")}
- Reason for Country choice: {g_info.get("reason_country")}
- Future Career Aspirations: {g_info.get("career_aspirations")}

ADDITIONAL BACKGROUND INFORMATION:
- Extracurriculars: {add_info.get("extracurriculars", "N/A")}
- Leadership experience: {add_info.get("leadership", "N/A")}
- Volunteer Work: {add_info.get("volunteer_work", "N/A")}
- Awards: {add_info.get("awards", "N/A")}
- Obstacles/Challenges: {add_info.get("challenges", "N/A")}
- Hobbies: {add_info.get("hobbies", "N/A")}
- Extra Notes: {add_info.get("notes", "N/A")}
"""

    if not openai_client:
        logger.critical("OpenAI client not configured in SOP Service.")
        raise RuntimeError("AI SOP Generator service is unconfigured on the server.")

    try:
        logger.info("Requesting SOP draft from OpenAI...")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": get_sop_system_prompt()},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        content = response.choices[0].message.content
        if content:
            # Strip out backticks if OpenAI sends back ```html codeblocks
            content = content.replace("```html", "").replace("```", "").strip()
            return content
        raise RuntimeError("Empty response received from OpenAI SOP service.")
    except Exception as e:
        logger.error(f"OpenAI SOP generation failed: {str(e)}.")
        raise RuntimeError(f"AI SOP draft generation failed: {str(e)}")


def rewrite_sop_segment(content: str, instruction: str, selected_text: Optional[str] = None) -> str:
    """
    Rewrites the full document or a targeted selected text block according to instruction commands.
    Returns the updated block or document.
    """
    system_prompt = """You are an admissions editor. Your task is to modify the provided text block according to the exact instructions.
Ensure you return only the edited text, matching the original format (HTML). Keep the original HTML tags (e.g. <h2>, <p>) intact. 
Output ONLY the resulting text. No preambles or chat explanations.
"""
    
    instruction_prompts = {
        "improve_grammar": "Improve grammar, correct typing mistakes, enhance sentence flow, and fix syntax issues.",
        "more_professional": "Elevate the tone of the text. Make it read more professional, ambitious, and academically rigorous.",
        "more_human": "Rewrite the text to sound organic, removing any typical robotic, monotonous AI expressions.",
        "reduce_ai": "Scan for and rewrite repetitive words and monotonous passive sentences to lower AI detection signature score.",
        "shorten": "Shorten and condense the paragraphs to be more direct, clear, and punchy, while retaining all core factual statements.",
        "expand": "Elaborate and expand on the experiences mentioned. Provide deeper reflections, details, and impact descriptions.",
        "vocabulary": "Upgrade vocabulary terms to sophisticated academic synonyms suitable for top-tier graduate reviews.",
        "simple": "Simplify the sentence structures. Make it direct, accessible, and very easy to read.",
        "default": "Improve the flow and vocabulary."
    }

    instruction_text = instruction_prompts.get(instruction, instruction_prompts["default"])
    target_block = selected_text if selected_text else content
    
    prompt = f"""Instruction: {instruction_text}
    
Text to modify:
{target_block}
"""

    if not openai_client:
        logger.critical("OpenAI client not configured in SOP Service for rewrite.")
        raise RuntimeError("AI SOP Rewrite service is unconfigured on the server.")

    try:
        logger.info(f"Requesting SOP rewrite block for instruction: {instruction}")
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=2000
        )
        revised = response.choices[0].message.content
        if revised:
            revised = revised.replace("```html", "").replace("```", "").strip()
            if selected_text:
                # Replace the old selected text with the new one inside the full document content
                return content.replace(selected_text, revised)
            return revised
        raise RuntimeError("Empty response received from OpenAI SOP rewrite service.")
    except Exception as e:
        logger.error(f"OpenAI SOP rewrite block failed: {str(e)}.")
        raise RuntimeError(f"AI SOP segment rewrite command failed: {str(e)}")


def get_fallback_sop_html(profile: Dict[str, Any]) -> str:
    """
    Deterministic fallback SOP generator to ensure system resilience when OpenAI API keys are not loaded.
    """
    p_info = profile.get("personal_info", {})
    a_info = profile.get("academic_background", {})
    w_info = profile.get("professional_experience", {})
    t_info = profile.get("target_education", {})
    g_info = profile.get("career_goals", {})

    name = p_info.get("full_name", "Applicant")
    course = t_info.get("course", "Postgraduate Studies")
    univ = t_info.get("university", "Target University")
    country = t_info.get("country", "Target Country")
    
    academic_university = a_info.get("university", "Undergraduate University")
    qualification = a_info.get("highest_qualification", "Bachelors Degree")
    cgpa = a_info.get("cgpa_percentage", "first-class marks")
    grad_year = a_info.get("graduation_year", "2024")
    
    skills = w_info.get("technical_skills", "analytical problem solving")
    experience = w_info.get("work_experience", "0")
    short_term = g_info.get("short_term_goals", "join a leading firm")
    long_term = g_info.get("long_term_goals", "become a key decision maker in my industry")
    
    return f"""<h2>Introduction</h2>
<p>My decision to pursue the {course} at the prestigious {univ} in {country} stems from my core ambition to integrate my existing foundations with advanced methodological frameworks. I aim to dedicate my career to solving complex problems and contributing to innovative solutions in the domain of {course}.</p>

<h2>Academic Background</h2>
<p>During my previous studies at {academic_university}, where I earned my {qualification} in {grad_year}, I was exposed to the fundamental structures of my discipline. Throughout my academic tenure, I maintained a robust track record, graduating with a CGPA/score of {cgpa}. This curriculum equipped me with core theoretical understandings and strong quantitative abilities, allowing me to secure multiple academic milestones.</p>

<h2>Professional and Project Experience</h2>
<p>In addition to theoretical work, I have consistently sought out practical application opportunities. With {experience} years of direct professional exposure, I have worked on real-world projects that demand {skills}. These experiences refined my collaborative skills, tested my technical abilities, and introduced me to advanced engineering workflows.</p>

<h2>Why Choose {univ}?</h2>
<p>The academic infrastructure at {univ} is uniquely aligned with my academic targets. The research conducted in their departments matches my specific study interests. I look forward to study under their distinguished faculty, whose contributions inspire my own research plans.</p>

<h2>Career Aspirations and Goals</h2>
<p>Immediately upon graduation, my short-term plan is to {short_term}, applying my practical learnings in an active industry setting. In the long term, I aspire to {long_term}, taking on leadership responsibilities and steering initiatives that bridge the gap between academic research and commercial impact.</p>

<h2>Conclusion</h2>
<p>Given my academic track record, practical technical skills, and clear vision, I am confident that I will be a valuable addition to {univ}. I look forward to starting my academic journey and contributing to the campus community.</p>
"""
