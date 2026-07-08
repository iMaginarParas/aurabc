import json
import logging
from openai import OpenAI
from fastapi import HTTPException, status
from ..config import settings
from ..prompts.eligibility_prompts import SYSTEM_PROMPT, format_eligibility_prompt
from ..schemas import AIResultEvaluation

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = None
if settings.openai_api_key:
    client = OpenAI(api_key=settings.openai_api_key)
else:
    logger.warning("OPENAI_API_KEY is not configured in settings.")

def evaluate_student_profile(profile_dict: dict) -> AIResultEvaluation:
    """
    Sends the student profile details to the OpenAI API and returns a structured evaluation.
    Rejects requests and throws error in production if the AI service fails or is unconfigured.
    """
    if not client:
        logger.critical("OpenAI client uninitialized. Cannot evaluate student profile.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI profile evaluation service is not configured on the server."
        )

    user_prompt = format_eligibility_prompt(profile_dict)
    
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
        logger.error(f"OpenAI API call or parsing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OpenAI service request failed: {str(e)}"
        )
