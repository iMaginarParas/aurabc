import logging
from sqlalchemy.orm import Session
from openai import AsyncOpenAI
from fastapi import HTTPException, status
from typing import AsyncGenerator, List, Dict, Any

from app.config import settings
from app.models import ChatMessage, AIUsageLog
from app.services.prompts.prompt_manager import PromptManager
from app.services.context.context_engine import ContextEngine

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        # Initialize AsyncOpenAI client
        api_key = settings.openai_api_key or ""
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    def _approximate_tokens(self, text: str) -> int:
        """
        Quick helper to approximate token usage (approx. 4 characters per token).
        Used when tiktoken is not available.
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    async def get_streaming_response(
        self,
        db: Session,
        session_id: str,
        user_id: str,
        user_email: str,
        history: List[ChatMessage],
        new_user_message_content: str
    ) -> AsyncGenerator[str, None]:
        """
        Sends the entire context + message history to OpenAI chat completions
        and yields response chunks in real-time. Logs token usage at the end.
        """
        if not self.client:
            logger.error("OPENAI_API_KEY is not configured in the environment.")
            yield "Error: OPENAI_API_KEY is not configured on the server. Please add it to your backend .env file to enable Aura AI."
            return

        try:
            # 1. Fetch system prompt
            system_prompt = PromptManager.get_system_prompt()

            # 2. Query dynamic student context and compile it
            student_context = ContextEngine.get_student_context_data(db, user_id, user_email)
            compiled_context = ContextEngine.compile_context_prompt(student_context)

            # Combined core system instructions
            full_system_instructions = f"{system_prompt}\n{compiled_context}"

            # 3. Assemble message payload for GPT-4
            # Keep system prompt at index 0
            messages: List[Dict[str, str]] = [
                {"role": "system", "content": full_system_instructions}
            ]

            # Append historical messages (limit history size to preserve context window)
            # Take the last 12 messages of the history
            for msg in history[-12:]:
                messages.append({"role": msg.role, "content": msg.content})

            # Append current user prompt
            messages.append({"role": "user", "content": new_user_message_content})

            # 4. Stream call OpenAI
            # Using gpt-4o-mini as a high-speed, cost-effective default model (or fallback to gpt-4)
            model_name = "gpt-4"
            response = await self.client.chat.completions.create(
                model=model_name,
                messages=messages,
                stream=True,
                temperature=0.7
            )

            assistant_reply_accumulated = []
            async for chunk in response:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    assistant_reply_accumulated.append(delta)
                    yield delta

            # 5. Calculate and log token consumption
            accumulated_text = "".join(assistant_reply_accumulated)
            
            # Simple token estimation
            prompt_payload_text = full_system_instructions + "\n".join([m["content"] for m in messages[1:]])
            prompt_tokens = self._approximate_tokens(prompt_payload_text)
            completion_tokens = self._approximate_tokens(accumulated_text)
            total_tokens = prompt_tokens + completion_tokens

            # Save token logs to database
            db_log = AIUsageLog(
                user_id=user_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model_name=model_name
            )
            db.add(db_log)
            db.commit()

        except Exception as e:
            logger.error(f"OpenAI Chat completion streaming error: {str(e)}")
            yield f"\n[AI Service Error]: Failed to generate response from OpenAI. Details: {str(e)}"
