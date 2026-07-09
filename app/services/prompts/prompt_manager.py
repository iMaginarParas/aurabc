import os

class PromptManager:
    @staticmethod
    def get_system_prompt() -> str:
        """
        Reads the primary system prompt from the system_prompt.txt file.
        Provides a fallback if the file is not found.
        """
        prompt_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        prompt_path = os.path.join(prompt_dir, "prompts", "system_prompt.txt")
        
        if os.path.exists(prompt_path):
            try:
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        
        # Hardcoded fallback system prompt
        return (
            "You are Aura AI, the primary global career advisor at Aura Routes AI. "
            "Help students intelligently using their profile data. Answer global career pathways, admissions, "
            "visas, and SOP queries in clear markdown."
        )
