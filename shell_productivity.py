import asyncio
import time
import json
import os
from datetime import datetime, timedelta
from shell_safe_executor import god_tier_tool as function_tool
import logging

logger = logging.getLogger("shell_productivity")

# File paths for persistent storage
TASKS_FILE = "shell_tasks.json"
DAILY_PLANS_FILE = "shell_daily_plans.json"
HABITS_FILE = "shell_habits.json"
NOTES_FILE = "shell_notes.json"

# Global list to track active timer/alarm/pomodoro tasks
_active_timers = []

# ============================================================
#  HELPER FUNCTIONS
# ============================================================

async def _safe_alert_beep(frequency: int = 1000, duration_ms: int = 250) -> None:
    """Best-effort timer alert that never fails the background timer task."""
    try:
        if os.name == "nt":
            import winsound

            winsound.Beep(frequency, duration_ms)
        else:
            print("\a", end="", flush=True)
    except Exception as e:
        logger.debug("timer alert beep unavailable: %s", e)
    await asyncio.sleep(0)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error("tasks file corrupt (JSONDecodeError): %s", e)
        except OSError as e:
            logger.error("tasks file read failed: %s", e)
    return []

def save_tasks(tasks):
    # Atomic write-then-replace: a crash between open+write can no longer
    # leave a half-written TASKS_FILE that load_tasks() would then wipe.
    tmp = TASKS_FILE + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(tasks, f, indent=2)
        os.replace(tmp, TASKS_FILE)
    except OSError as e:
        logger.error("save_tasks failed: %s", e)

def _load_json(filepath, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning("%s corrupt (JSONDecodeError): %s", filepath, e)
        except OSError as e:
            logger.warning("%s read failed: %s", filepath, e)
    return default

def _save_json(filepath, data):
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, filepath)
    except OSError as e:
        logger.error("_save_json failed (%s): %s", filepath, e)

# ============================================================
#  UPGRADED: manage_tasks_tool
#  Now supports: done, priority, due_date
# ============================================================

@function_tool
async def manage_tasks_tool(action: str, task_text: str = "", priority: str = "medium", due_date: str = "") -> str:
    """
    Manages a persistent To-Do list.
    Args:
        action: 'add', 'list', 'remove', 'done', 'clear'.
        task_text: The task description (required for 'add', 'remove', 'done').
        priority: 'high', 'medium', 'low' (optional, default 'medium').
        due_date: Optional due date in YYYY-MM-DD format.
    """
    try:
        tasks = load_tasks()

        if action == "add":
            if not task_text:
                return "❌ Task text required for 'add'. Bhai task toh batao!"
            if priority not in ("high", "medium", "low"):
                priority = "medium"
            task = {
                "id": (max(t["id"] for t in tasks) + 1) if tasks else 1,
                "text": task_text,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "priority": priority,
                "due_date": due_date if due_date else None,
                "status": "pending"
            }
            tasks.append(task)
            save_tasks(tasks)
            extra = ""
            if due_date:
                extra += f" | Due: {due_date}"
            return f"✅ Task added: '{task_text}' [Priority: {priority.upper()}]{extra} — Kaam list mein aa gaya!"

        elif action == "list":
            if not tasks:
                return "📝 Koi active task nahi hai. List khaali hai boss!"
            output = ["--- 📋 TO-DO LIST ---"]
            priority_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for t in tasks:
                p_icon = priority_icons.get(t.get("priority", "medium"), "🟡")
                status = "✅" if t.get("status") == "done" else "⏳"
                line = f"{status} {t['id']}. {p_icon} {t['text']} ({t['date']})"
                if t.get("due_date"):
                    line += f" | Due: {t['due_date']}"
                if t.get("status") == "done":
                    line += " [DONE]"
                output.append(line)
            return "\n".join(output)

        elif action == "remove":
            new_tasks = [t for t in tasks if str(t['id']) != task_text and task_text.lower() not in t['text'].lower()]
            if len(new_tasks) < len(tasks):
                save_tasks(new_tasks)
                return f"✅ Task removed: '{task_text}' — Hata diya list se!"
            return "⚠️ Koi matching task nahi mila remove karne ke liye."

        elif action == "done":
            if not task_text:
                return "❌ Task ID ya text toh batao 'done' mark karne ke liye!"
            found = False
            for t in tasks:
                if str(t['id']) == task_text or task_text.lower() in t['text'].lower():
                    t['status'] = "done"
                    found = True
                    break
            if found:
                save_tasks(tasks)
                return f"✅ Task '{task_text}' done mark ho gaya! Shabaash! 🎉"
            return "⚠️ Koi matching task nahi mila done karne ke liye."

        elif action == "clear":
            save_tasks([])
            return "🗑️ Saari tasks clear ho gayi. Fresh start!"

        return "❌ Unknown action. Use: add, list, remove, done, clear."
    except Exception as e:
        return f"❌ Task Error: {e}"

# ============================================================
#  UPGRADED: set_timer_tool
#  Now supports seconds parameter and tracks active timers
# ============================================================

@function_tool
async def set_timer_tool(minutes: int = 0, seconds: int = 0, reason: str = "Timer") -> str:
    """
    Sets a countdown timer for a specific number of minutes and/or seconds.
    Example: "Set a timer for 10 minutes for pasta" or "30 seconds timer".
    Args:
        minutes: Number of minutes (default 0).
        seconds: Number of seconds (default 0).
        reason: Reason/label for the timer.
    """
    try:
        total_seconds = (minutes * 60) + seconds
        if total_seconds <= 0:
            return "❌ Bhai, time toh positive hona chahiye! Minutes ya seconds do."
        target_time = datetime.now() + timedelta(seconds=total_seconds)

        task = asyncio.create_task(_timer_countdown(total_seconds, reason))
        _active_timers.append({"task": task, "reason": reason, "target": target_time.strftime('%H:%M:%S')})

        time_str = ""
        if minutes > 0:
            time_str += f"{minutes} minute(s)"
        if seconds > 0:
            time_str += f" {seconds} second(s)" if time_str else f"{seconds} second(s)"

        return f"⏰ Timer set for {time_str} ({reason}). Alert at {target_time.strftime('%H:%M:%S')}. Chill karo, mai bata dunga!"
    except Exception as e:
        return f"❌ Error setting timer: {str(e)}"

async def _timer_countdown(seconds, reason):
    """Internal background task for timer"""
    await asyncio.sleep(seconds)
    logger.info(f"⏰ TIMER DONE: {reason}")
    for _ in range(3):
        await _safe_alert_beep(1000, 500)
        await asyncio.sleep(0.5)

# ============================================================
#  set_alarm_tool (unchanged)
# ============================================================

@function_tool
async def set_alarm_tool(time_str: str, reason: str = "Alarm") -> str:
    """
    Sets an alarm for a specific time (HH:MM format, 24-hour).
    Example: "Set alarm for 17:30".
    """
    try:
        now = datetime.now()
        try:
            target = datetime.strptime(time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        except ValueError:
            return "❌ Invalid format. Please use HH:MM (e.g., 14:30)."

        if target < now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()

        task = asyncio.create_task(_timer_countdown(wait_seconds, reason))
        _active_timers.append({"task": task, "reason": reason, "target": target.strftime('%H:%M:%S')})

        return f"🔔 Alarm set for {target.strftime('%H:%M')} ({reason}). Mai jaaga rahunga!"
    except Exception as e:
        return f"❌ Error setting alarm: {str(e)}"

# ============================================================
#  UPGRADED: stop_all_timers_tool
#  Now actually cancels tracked tasks
# ============================================================

@function_tool
async def stop_all_timers_tool() -> str:
    """
    Stops/Cancels all active timers, alarms, and pomodoro sessions.
    """
    global _active_timers
    if not _active_timers:
        return "⚠️ Koi active timer/alarm nahi hai cancel karne ke liye."

    cancelled = 0
    for entry in _active_timers:
        t = entry.get("task")
        if t and not t.done():
            t.cancel()
            cancelled += 1

    _active_timers.clear()
    return f"🛑 {cancelled} timer(s)/alarm(s) cancel ho gaye! Sab band boss."

# ============================================================
#  NEW TOOL 1: pomodoro_tool
# ============================================================

@function_tool
async def pomodoro_tool(work_minutes: int = 25, break_minutes: int = 5, cycles: int = 1) -> str:
    """
    Starts a Pomodoro focus session with work and break periods.
    Args:
        work_minutes: Work period in minutes (default 25).
        break_minutes: Break period in minutes (default 5).
        cycles: Number of work-break cycles (default 1).
    """
    try:
        if work_minutes <= 0 or break_minutes <= 0 or cycles <= 0:
            return "❌ Bhai, sab values positive honi chahiye!"

        task = asyncio.create_task(_pomodoro_session(work_minutes, break_minutes, cycles))
        _active_timers.append({"task": task, "reason": f"Pomodoro ({cycles} cycles)", "target": "running"})

        total_time = (work_minutes + break_minutes) * cycles
        return (
            f"🍅 Pomodoro shuru! {cycles} cycle(s) — {work_minutes}min kaam + {break_minutes}min break.\n"
            f"⏱️ Total estimated time: {total_time} minutes.\n"
            f"Focus mode ON hai boss! Kaam pe lag jao! 💪"
        )
    except Exception as e:
        return f"❌ Pomodoro Error: {e}"

async def _pomodoro_session(work_minutes, break_minutes, cycles):
    """Internal background task for Pomodoro cycles"""
    try:
        for cycle in range(1, cycles + 1):
            logger.info(f"🍅 Pomodoro Cycle {cycle}/{cycles} — WORK START ({work_minutes} min)")
            # Work period
            await asyncio.sleep(work_minutes * 60)
            # Work done beep — 3 short beeps
            for _ in range(3):
                await _safe_alert_beep(1200, 300)
                await asyncio.sleep(0.3)
            logger.info(f"🍅 Pomodoro Cycle {cycle}/{cycles} — BREAK START ({break_minutes} min)")

            if cycle < cycles:
                # Break period (skip break after last cycle)
                await asyncio.sleep(break_minutes * 60)
                # Break done beep — 2 low beeps
                for _ in range(2):
                    await _safe_alert_beep(800, 400)
                    await asyncio.sleep(0.4)

        # All cycles done — long celebration beep
        for _ in range(5):
            await _safe_alert_beep(1500, 200)
            await asyncio.sleep(0.2)
        logger.info(f"🍅 Pomodoro session COMPLETE! All {cycles} cycle(s) done.")
    except asyncio.CancelledError:
        logger.info("🍅 Pomodoro session cancelled.")
    except Exception as e:
        logger.error(f"🍅 Pomodoro error: {e}")

# ============================================================
#  NEW TOOL 2: daily_planner_tool
# ============================================================

@function_tool
async def daily_planner_tool(action: str = "show") -> str:
    """
    A daily planner with date-based entries.
    Args:
        action: 'show' (today's plan), 'add <text>' (add to today), 'clear' (clear today).
    """
    try:
        plans = _load_json(DAILY_PLANS_FILE, {})
        today = datetime.now().strftime("%Y-%m-%d")

        if action == "show":
            today_plan = plans.get(today, [])
            if not today_plan:
                return f"📅 Aaj ({today}) ka koi plan nahi hai. 'add' karke plan banao!"
            output = [f"--- 📅 DAILY PLAN: {today} ---"]
            for i, item in enumerate(today_plan, 1):
                output.append(f"  {i}. {item}")
            return "\n".join(output)

        elif action.startswith("add "):
            text = action[4:].strip()
            if not text:
                return "❌ Plan text toh likho! 'add meeting at 3pm' jaisa kuch."
            if today not in plans:
                plans[today] = []
            plans[today].append(text)
            _save_json(DAILY_PLANS_FILE, plans)
            return f"✅ Plan mein add ho gaya: '{text}' — Aaj ka din productive hoga! 💪"

        elif action == "clear":
            plans[today] = []
            _save_json(DAILY_PLANS_FILE, plans)
            return f"🗑️ Aaj ({today}) ka poora plan clear ho gaya!"

        else:
            return "❌ Unknown action. Use: 'show', 'add <text>', 'clear'."
    except Exception as e:
        return f"❌ Planner Error: {e}"

# ============================================================
#  NEW TOOL 3: habit_tracker_tool
# ============================================================

@function_tool
async def habit_tracker_tool(action: str = "status", habit_name: str = "") -> str:
    """
    Track daily habits with streak counting.
    Args:
        action: 'add', 'done', 'status', 'remove'.
        habit_name: Name of the habit (required for add, done, remove).
    """
    try:
        habits = _load_json(HABITS_FILE, {})
        today = datetime.now().strftime("%Y-%m-%d")

        if action == "add":
            if not habit_name:
                return "❌ Habit ka naam toh batao! e.g., 'exercise', 'reading'"
            habit_key = habit_name.lower().strip()
            if habit_key in habits:
                return f"⚠️ '{habit_name}' habit pehle se hai list mein!"
            habits[habit_key] = {"name": habit_name, "dates": [], "created": today}
            _save_json(HABITS_FILE, habits)
            return f"✅ Habit added: '{habit_name}' — Consistency is key boss! 🔑"

        elif action == "done":
            if not habit_name:
                return "❌ Kaunsi habit done hui? Naam batao."
            habit_key = habit_name.lower().strip()
            if habit_key not in habits:
                return f"⚠️ '{habit_name}' habit list mein nahi hai. Pehle 'add' karo."
            if today in habits[habit_key]["dates"]:
                return f"⚡ '{habit_name}' aaj pehle se done hai! Double kaam nahi boss."
            habits[habit_key]["dates"].append(today)
            _save_json(HABITS_FILE, habits)
            streak = _calculate_streak(habits[habit_key]["dates"])
            return f"✅ '{habit_name}' done for today! 🔥 Current streak: {streak} day(s). Keep going!"

        elif action == "status":
            if not habits:
                return "📊 Koi habit track nahi ho rahi. 'add' karke shuru karo!"
            output = ["--- 📊 HABIT TRACKER ---"]
            for key, data in habits.items():
                streak = _calculate_streak(data["dates"])
                done_today = "✅" if today in data["dates"] else "❌"
                total = len(data["dates"])
                output.append(f"  {done_today} {data['name']} — Streak: {streak} day(s) | Total: {total}")
            return "\n".join(output)

        elif action == "remove":
            if not habit_name:
                return "❌ Kaunsi habit remove karni hai? Naam batao."
            habit_key = habit_name.lower().strip()
            if habit_key not in habits:
                return f"⚠️ '{habit_name}' habit mili nahi list mein."
            del habits[habit_key]
            _save_json(HABITS_FILE, habits)
            return f"✅ Habit '{habit_name}' remove ho gayi. Bye bye! 👋"

        else:
            return "❌ Unknown action. Use: 'add', 'done', 'status', 'remove'."
    except Exception as e:
        return f"❌ Habit Tracker Error: {e}"

def _calculate_streak(dates_list):
    """Calculate current consecutive day streak from today backwards."""
    if not dates_list:
        return 0
    sorted_dates = sorted(set(dates_list), reverse=True)
    today = datetime.now().date()
    streak = 0
    for i, d_str in enumerate(sorted_dates):
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        expected = today - timedelta(days=i)
        if d == expected:
            streak += 1
        else:
            break
    return streak

# ============================================================
#  NEW TOOL 4: quick_note_tool
# ============================================================

@function_tool
async def quick_note_tool(action: str = "list", note_text: str = "") -> str:
    """
    Quick sticky notes with timestamps.
    Args:
        action: 'add', 'list', 'clear', 'search'.
        note_text: Text for 'add' or query for 'search'.
    """
    try:
        notes = _load_json(NOTES_FILE, [])

        if action == "add":
            if not note_text:
                return "❌ Note text toh likho! Kya yaad rakhna hai?"
            note = {
                "id": (max(n["id"] for n in notes) + 1) if notes else 1,
                "text": note_text,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            notes.append(note)
            _save_json(NOTES_FILE, notes)
            return f"📌 Note saved: '{note_text}' — Yaad rakh lunga boss!"

        elif action == "list":
            if not notes:
                return "📝 Koi notes nahi hai. 'add' karke likho kuch!"
            output = ["--- 📌 QUICK NOTES ---"]
            for n in notes:
                output.append(f"  [{n['id']}] {n['text']} ({n['timestamp']})")
            return "\n".join(output)

        elif action == "clear":
            _save_json(NOTES_FILE, [])
            return "🗑️ Saare notes clear ho gaye! Clean slate."

        elif action == "search" or action.startswith("search "):
            query = note_text if note_text else (action[7:].strip() if action.startswith("search ") else "")
            if not query:
                return "❌ Search kya karna hai? Query toh do."
            results = [n for n in notes if query.lower() in n["text"].lower()]
            if not results:
                return f"🔍 '{query}' se koi note nahi mila."
            output = [f"--- 🔍 SEARCH: '{query}' ---"]
            for n in results:
                output.append(f"  [{n['id']}] {n['text']} ({n['timestamp']})")
            return "\n".join(output)

        else:
            return "❌ Unknown action. Use: 'add', 'list', 'clear', 'search'."
    except Exception as e:
        return f"❌ Quick Note Error: {e}"
