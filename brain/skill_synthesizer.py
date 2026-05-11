
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("SkillSynthesizer")

class SkillSynthesizer:
    """
    🧬 SELF-EVOLUTION ENGINE
    
    Capabilities:
    - Pattern Recognition: Identifies successful workflows.
    - Skill Extraction: Converts execution logs into reusable 'Spells'.
    - Optimization: Refines skills based on execution metrics (speed/success rate).
    """
    
    def __init__(self):
        self.skills_db_path = "brain/data/skills.json"
        self.learned_skills = self._load_skills()
        
    def _load_skills(self) -> Dict[str, Any]:
        try:
            with open(self.skills_db_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.error(f"Failed to load skills: {e}")
            return {}

    def save_skill(self, trigger: str, plan: List[Dict], meta: Dict = None):
        """
        Learns a new skill from a successful generalized execution.
        """
        skill_id = self._generate_skill_id(trigger)
        
        new_skill = {
            "id": skill_id,
            "trigger_pattern": trigger, # In real ASI, this would be an embedding
            "plan_template": plan,
            "created_at": datetime.now().isoformat(),
            "times_used": 0,
            "success_rate": 1.0,
            "meta": meta or {}
        }
        
        self.learned_skills[skill_id] = new_skill
        self._persist_db()
        logger.info(f"🧬 New Skill Synthesized: {skill_id}")

    def get_skill(self, query: str) -> Optional[Dict]:
        """
        Retrieves a learned skill that matches the query.
        """
        # Simple exact match/keyword match for now
        # A real ASI would use semantic search here
        for skill_id, skill in self.learned_skills.items():
            if skill["trigger_pattern"] in query:
                skill["times_used"] += 1
                return skill
        return None

    def _persist_db(self):
        try:
            with open(self.skills_db_path, 'w') as f:
                json.dump(self.learned_skills, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skills DB: {e}")

    def _generate_skill_id(self, trigger: str) -> str:
        return f"skill_{abs(hash(trigger))}"

# Singleton
skill_synthesizer = SkillSynthesizer()
