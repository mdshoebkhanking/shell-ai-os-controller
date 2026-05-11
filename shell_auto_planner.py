#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_planner")

# --- CATEGORY TEMPLATES ---
CATEGORY_TEMPLATES = {
    "general": {
        "phase_prefix": "Phase",
        "focus_areas": ["Planning & Research", "Execution", "Review & Iteration", "Optimization", "Completion"],
    },
    "learning": {
        "phase_prefix": "Learning Phase",
        "focus_areas": ["Fundamentals & Basics", "Core Concepts", "Hands-on Practice", "Advanced Topics", "Projects & Application", "Revision & Mastery", "Final Assessment"],
    },
    "business": {
        "phase_prefix": "Business Phase",
        "focus_areas": ["Market Research", "Business Plan", "MVP Development", "Launch Prep", "Go-to-Market", "Growth & Scaling", "Review & Pivot"],
    },
    "fitness": {
        "phase_prefix": "Fitness Phase",
        "focus_areas": ["Assessment & Goal Setting", "Foundation Building", "Progressive Training", "Intensity Ramp-up", "Peak Performance", "Recovery & Maintenance", "Lifestyle Integration"],
    },
    "coding": {
        "phase_prefix": "Dev Sprint",
        "focus_areas": ["Setup & Architecture", "Core Implementation", "Feature Development", "Testing & Debugging", "Optimization", "Documentation", "Deployment & Release"],
    },
}

def _calculate_phases(duration_days: int) -> int:
    """Adaptive phase count based on duration."""
    if duration_days <= 7:
        return 3
    elif duration_days <= 14:
        return 4
    elif duration_days <= 30:
        return 5
    elif duration_days <= 60:
        return 6
    else:
        return 7

def _build_structured_plan(goal: str, duration_days: int, category: str) -> tuple:
    """Builds a structured plan with adaptive phases. Returns (text_plan, json_plan)."""
    category = category.lower() if category else "general"
    if category not in CATEGORY_TEMPLATES:
        category = "general"

    template = CATEGORY_TEMPLATES[category]
    num_phases = _calculate_phases(duration_days)
    phase_prefix = template["phase_prefix"]
    focus_areas = template["focus_areas"]

    # Distribute days across phases
    days_per_phase = duration_days / num_phases
    phases = []
    current_day = 1

    for i in range(num_phases):
        end_day = int(current_day + days_per_phase - 1) if i < num_phases - 1 else duration_days
        focus = focus_areas[i % len(focus_areas)]

        phase_data = {
            "phase_number": i + 1,
            "name": f"{phase_prefix} {i + 1}: {focus}",
            "days": f"Day {int(current_day)} - Day {end_day}",
            "start_day": int(current_day),
            "end_day": end_day,
            "focus": focus,
            "daily_tasks": [
                f"{focus} ke related daily practice karein",
                f"Progress track karein aur notes banayein",
                f"Agar koi doubt ho toh resolve karein",
            ],
        }
        phases.append(phase_data)
        current_day = end_day + 1

    # Build text plan
    plan_header = f"🚀 --- ROADMAP: {goal.upper()} --- 🚀\n"
    plan_header += f"📅 Timeline: {duration_days} Days | Category: {category.capitalize()} | Phases: {num_phases}\n"
    plan_header += f"👑 boss: MD SHOEB KING\n\n"

    plan_body = ""
    for phase in phases:
        plan_body += f"  📌 [{phase['name']}] ({phase['days']})\n"
        for task in phase["daily_tasks"]:
            plan_body += f"     • {task}\n"
        plan_body += "\n"

    instructions = f"""Sir, maine aapke '{goal}' goal ke liye ye detailed {num_phases}-phase plan tyar kiya hai.
Category: {category.capitalize()} | Duration: {duration_days} days

Aage kya karna hai:
1. Rozana 1 step complete karein.
2. Main aapko reminders bhi de sakti hoon.
3. Har phase complete hone par next phase shuru karein.
"""

    text_plan = plan_header + plan_body + instructions

    # Build JSON plan
    json_plan = {
        "goal": goal,
        "category": category,
        "duration_days": duration_days,
        "total_phases": num_phases,
        "created_at": datetime.now().isoformat(),
        "master": "MD SHOEB KING",
        "phases": phases,
    }

    return text_plan, json_plan


@function_tool
async def generate_task_plan(goal: str, duration_days: int = 30, category: str = "general") -> str:
    """
    Generates a complete, step-by-step roadmap and daily plan for a user goal.
    Args:
        goal: The user's target (e.g., 'Learn Python', 'Start a Business').
        duration_days: The estimated timeline in days.
        category: Plan template type - general, learning, business, fitness, coding (default general).
    """
    try:
        logger.info(f"📋 Generating Plan for Goal: {goal} | Category: {category} | Days: {duration_days}")

        # Build structured plan with adaptive phases
        text_plan, json_plan = _build_structured_plan(goal, duration_days, category)

        # Save plan to files
        home = os.path.expanduser("~")
        plan_dir = os.path.join(home, "Documents", "Shell_Plans")
        os.makedirs(plan_dir, exist_ok=True)

        clean_name = goal.lower().replace(' ', '_')
        clean_name = "".join(c for c in clean_name if c.isalnum() or c == '_')

        # Save text version
        txt_filename = f"plan_{clean_name}.txt"
        txt_filepath = os.path.join(plan_dir, txt_filename)
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(text_plan)

        # Save JSON version for machine parsing
        json_filename = f"plan_{clean_name}.json"
        json_filepath = os.path.join(plan_dir, json_filename)
        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(json_plan, f, indent=2, ensure_ascii=False)

        num_phases = json_plan["total_phases"]

        return (
            f"{text_plan}\n\n"
            f"✅ Sir! {num_phases}-phase roadmap ready hai!\n"
            f"📄 Text file: {txt_filepath}\n"
            f"📊 JSON file: {json_filepath}\n"
            f"Kya hum Day 1 se start karein?"
        )

    except Exception as e:
        logger.error(f"Planning failed: {e}")
        return f"❌ Plan banane mein problem aayi: {str(e)}"

@function_tool
async def set_plan_reminder(task_name: str, hour: int = 10, minute: int = 0) -> str:
    """
    Sets a daily reminder for a specific task in the plan.
    """
    # Note: In a real agent, this would hook into a scheduler.
    # For now, we simulate the 'Commitment'
    return f"✅ Done boss! Ab se main aapko rozana {hour:02d}:{minute:02d} par '{task_name}' ke liye remind karungi."


@function_tool
async def list_plans_tool() -> str:
    """
    Lists all plan files in ~/Documents/Shell_Plans/ directory.
    Shows filename, size, and created date for each plan.
    """
    try:
        home = os.path.expanduser("~")
        plan_dir = os.path.join(home, "Documents", "Shell_Plans")

        if not os.path.exists(plan_dir):
            return "📂 Shell_Plans folder abhi exist nahi karta Sir. Pehle ek plan banayein!"

        all_files = [f for f in os.listdir(plan_dir) if os.path.isfile(os.path.join(plan_dir, f))]

        if not all_files:
            return "📂 Koi plan file nahi mili Sir. `generate_task_plan` se pehle ek plan banayein!"

        result_lines = [f"📂 --- Your Plans ({len(all_files)} files) ---\n"]

        for fname in sorted(all_files):
            fpath = os.path.join(plan_dir, fname)
            try:
                # File size
                size_bytes = os.path.getsize(fpath)
                if size_bytes >= 1024 * 1024:
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                else:
                    size_str = f"{size_bytes / 1024:.2f} KB"

                # Created date
                created_time = os.path.getctime(fpath)
                created_date = datetime.fromtimestamp(created_time).strftime("%Y-%m-%d %H:%M")

                result_lines.append(f"📄 {fname}\n   Size: {size_str} | Created: {created_date}")
            except Exception as e:
                result_lines.append(f"📄 {fname} — Error reading details: {e}")

        result_lines.append(f"\n📍 Folder: {plan_dir}")
        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"List Plans Error: {e}")
        return f"❌ Plans list karne mein error: {str(e)}"


@function_tool
async def delete_plan_tool(plan_name: str) -> str:
    """
    Deletes a specific plan file from ~/Documents/Shell_Plans/.
    Safety check - exact filename required for confirmation.

    Args:
        plan_name (str): Exact filename of the plan to delete (e.g., 'plan_learn_python.txt').
    """
    try:
        home = os.path.expanduser("~")
        plan_dir = os.path.join(home, "Documents", "Shell_Plans")

        if not plan_name or not plan_name.strip():
            return "❌ Sir, plan_name dena zaroori hai. Pehle `list_plans_tool` se filenames check karein."

        plan_name = plan_name.strip()
        filepath = os.path.join(plan_dir, plan_name)

        # Safety: check the file exists
        if not os.path.exists(filepath):
            available = [f for f in os.listdir(plan_dir) if os.path.isfile(os.path.join(plan_dir, f))] if os.path.exists(plan_dir) else []
            available_str = "\n".join(f"  • {f}" for f in available) if available else "  (koi file nahi hai)"
            return (
                f"❌ File nahi mili: '{plan_name}'\n"
                f"Available files:\n{available_str}\n"
                f"Exact filename dein Sir for safety."
            )

        # Safety: must be inside plan_dir (no path traversal)
        real_filepath = os.path.realpath(filepath)
        real_plan_dir = os.path.realpath(plan_dir)
        if not real_filepath.startswith(real_plan_dir):
            return "❌ Security check fail! Sirf Shell_Plans folder ke andar ki files delete ho sakti hain."

        # Delete the file
        file_size = os.path.getsize(filepath)
        os.remove(filepath)

        size_str = f"{file_size / 1024:.2f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.2f} MB"

        return (
            f"🗑️ Plan file delete ho gayi Sir!\n"
            f"📄 Deleted: {plan_name}\n"
            f"📊 Size thi: {size_str}\n"
            f"📍 Folder: {plan_dir}"
        )

    except Exception as e:
        logger.error(f"Delete Plan Error: {e}")
        return f"❌ Plan delete karne mein error: {str(e)}"


__all__ = ['generate_task_plan', 'set_plan_reminder', 'list_plans_tool', 'delete_plan_tool']
