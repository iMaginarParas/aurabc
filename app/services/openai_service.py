import os
import replicate
import json
import logging
from fastapi import HTTPException, status
from typing import Optional, List
from ..config import settings
from ..prompts.eligibility_prompts import SYSTEM_PROMPT, format_eligibility_prompt
from ..schemas import AIResultEvaluation

logger = logging.getLogger(__name__)


class ReplicateOpenAIMock:
    def __init__(self, api_key: str):
        if api_key:
            os.environ["REPLICATE_API_TOKEN"] = api_key
            
        class ChatCompletions:
            def create(self, model, messages, **kwargs):
                system_prompt = ""
                user_prompt = ""
                for msg in messages:
                    if isinstance(msg, dict):
                        role = msg.get("role")
                        content = msg.get("content")
                    else:
                        role = getattr(msg, "role", "")
                        content = getattr(msg, "content", "")
                        
                    if role == "system":
                        system_prompt = content
                    elif role == "user":
                        user_prompt = content
                
                replicate_model = f"openai/{model}" if not model.startswith("openai/") else model
                if replicate_model.startswith("openai/"):
                    replicate_model = "meta/meta-llama-3-70b-instruct"
                
                output = replicate.run(
                    replicate_model,
                    input={
                        "prompt": user_prompt,
                        "system_prompt": system_prompt,
                        "temperature": kwargs.get("temperature", 0.2)
                    }
                )
                
                content = "".join(output)
                
                class Message:
                    def __init__(self, content):
                        self.content = content
                
                class Choice:
                    def __init__(self, content):
                        self.message = Message(content)
                        
                class Response:
                    def __init__(self, content):
                        self.choices = [Choice(content)]
                        
                return Response(content)
                
        class Chat:
            def __init__(self):
                self.completions = ChatCompletions()
                
        self.chat = Chat()


# Initialize Replicate mock client
client = None
if settings.openai_api_key:
    if settings.openai_api_key.startswith("sk-"):
        import openai
        client = openai.OpenAI(api_key=settings.openai_api_key)
    else:
        client = ReplicateOpenAIMock(api_key=settings.openai_api_key)
else:
    logger.warning("OPENAI_API_KEY is not configured in settings.")

def evaluate_student_profile(profile_dict: dict, allowed_countries: Optional[List[str]] = None) -> AIResultEvaluation:
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
    if allowed_countries:
        user_prompt += f"\n\nCRITICAL SYSTEM FILTER CONSTRAINT: You are ONLY allowed to recommend universities and countries from the following list: {', '.join(allowed_countries)}. DO NOT output any recommendations outside this list."
    
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
