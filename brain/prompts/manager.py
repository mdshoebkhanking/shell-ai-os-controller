import os
import json
import logging
from typing import Dict, List, Optional

# Logger
logger = logging.getLogger("shell_prompt_engine")

# Template Directory
TEMPLATE_DIR = "brain/prompts/templates"

class PromptManager:
    """
    Advanced Prompt Engineering Engine.
    Manages Personas, Context Injection, and Dynamic Templates.
    """
    def __init__(self):
        self._ensure_dir()
        # Default Templates
        self.templates = {
            "default": {
                "system": "You are Shell AI, a helpful and intelligent assistant.",
                "user_format": "{{query}}"
            },
            "coder": {
                "system": "You are a World-Class Python Developer. Write clean, efficient, and documented code. Focus on modularity.",
                "user_format": "TASK: {{query}}\n\nCONTEXT:\n{{context}}"
            },
            "planner": {
                "system": "You are a Strategic Project Manager. Break down complex goals into small, actionable steps.",
                "user_format": "GOAL: {{query}}\n\nCreate a step-by-step plan."
            }
        }
        self._load_templates()

    def _ensure_dir(self):
        os.makedirs(TEMPLATE_DIR, exist_ok=True)

    def _load_templates(self):
        """Loads custom JSON templates from disk."""
        if not os.path.exists(TEMPLATE_DIR): return
        
        for filename in os.listdir(TEMPLATE_DIR):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(TEMPLATE_DIR, filename), 'r') as f:
                        data = json.load(f)
                        name = filename.replace(".json", "")
                        self.templates[name] = data
                except Exception as e:
                    logger.error(f"Failed to load template {filename}: {e}")

    def render_prompt(self, template_name: str, query: str, context: str = "") -> Dict[str, str]:
        """
        Renders the final system and user prompt based on template.
        """
        template = self.templates.get(template_name, self.templates["default"])
        
        system_prompt = template.get("system", "")
        user_format = template.get("user_format", "{{query}}")
        
        # Injection
        final_user = user_format.replace("{{query}}", query).replace("{{context}}", context)
        
        return {
            "system": system_prompt,
            "user": final_user
        }

    def list_templates(self) -> List[str]:
        return list(self.templates.keys())

# Singleton
prompt_manager = PromptManager()
