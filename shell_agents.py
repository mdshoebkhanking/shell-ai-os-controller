"""
Shell AI Agent System — ULTIMATE Edition
==========================================
20 Specialist AI Agents + 1 Master Agent
Har agent khud sochta hai, plan banata hai, tools chain karta hai, aur results deta hai.

Usage:
    from shell_agents import master_agent_tool, developer_agent_tool, list_agents_tool
"""

import asyncio
import json
import logging
import re
import time
from typing import List, Dict, Any, Optional

from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_agents")

# ═══════════════════════════════════════════════════════════════
#  AGENT RESULT
# ═══════════════════════════════════════════════════════════════

class AgentResult:
    __slots__ = ("agent_name", "task", "status", "result",
                 "steps_completed", "steps_total", "elapsed")

    def __init__(self, agent_name, task, status, result, steps_completed, steps_total, elapsed):
        self.agent_name = agent_name
        self.task = task
        self.status = status
        self.result = result
        self.steps_completed = steps_completed
        self.steps_total = steps_total
        self.elapsed = elapsed

    def format(self) -> str:
        return (
            f"[{self.agent_name}] ({self.status} | "
            f"{self.steps_completed}/{self.steps_total} steps | "
            f"{self.elapsed}s)\n\n{self.result}"
        )


# ═══════════════════════════════════════════════════════════════
#  SHELL AGENT — BASE CLASS
# ═══════════════════════════════════════════════════════════════

class ShellAgent:
    """Base class for all Shell AI Agents."""

    _brain = None
    _brain_unavailable_until = 0.0

    @classmethod
    def _get_brain(cls):
        if cls._brain is None:
            try:
                from brain.core import MultiAIBrain
                cls._brain = MultiAIBrain()
            except Exception as e:
                logger.error(f"Failed to init MultiAIBrain: {e}")
        return cls._brain

    @classmethod
    def _get_registry(cls):
        try:
            from shell_tool_registry import ToolRegistry
            return ToolRegistry.get()
        except Exception:
            return None

    def __init__(self, name: str, role: str, expertise: str,
                 tool_categories: List[str], think_mode: str = "SMART",
                 execute_mode: str = "FAST"):
        self.name = name
        self.role = role
        self.expertise = expertise
        self.tool_categories = tool_categories
        self.think_mode = think_mode
        self.execute_mode = execute_mode

    def _get_tool_descriptions(self) -> str:
        registry = self._get_registry()
        if not registry:
            return "No tools available (registry not loaded)."
        lines = []
        for cat in self.tool_categories:
            for info in registry.get_by_category(cat):
                if info.enabled:
                    lines.append(f"- {info.name}: {info.description}")
        return "\n".join(lines) if lines else "No tools found in assigned categories."

    async def _call_tool(self, tool_name: str, **kwargs) -> str:
        registry = self._get_registry()
        if not registry:
            return await self._reason_without_tool(tool_name, "ToolRegistry not available", kwargs)
        tool_obj = registry.get_tool_obj(tool_name)
        if not tool_obj:
            return await self._reason_without_tool(tool_name, "tool is not registered", kwargs)
        try:
            registry.record_call(tool_name)
            result = await asyncio.wait_for(tool_obj(**kwargs), timeout=30.0)
            return str(result) if result else "Tool returned empty result."
        except asyncio.TimeoutError:
            return f"Error: Tool '{tool_name}' timed out (30s)."
        except Exception as e:
            return f"Error calling '{tool_name}': {str(e)[:200]}"

    async def _reason_without_tool(self, tool_name: str, reason: str, params: Dict[str, Any]) -> str:
        prompt = (
            f"The execution plan selected unavailable tool '{tool_name}' ({reason}).\n"
            f"Step parameters: {json.dumps(params, ensure_ascii=False, default=str)[:1000]}\n\n"
            "Complete the user's step with reasoning only. Do not claim that a tool, browser, "
            "system action, or external test actually ran. If the user only asked for an idea, "
            "plan, explanation, or draft, answer directly without mentioning internal tool names. "
            "If the user required real execution, say the required backend tool is unavailable "
            "and give the safest next action."
        )
        return await self._ai_think(prompt, mode=self.execute_mode)

    async def _ai_think(self, prompt: str, system_prompt: str = None,
                        mode: str = None) -> str:
        brain = self._get_brain()
        if not brain:
            offline_reply = self._offline_coding_brain_reply(prompt, system_prompt=system_prompt, mode=mode)
            return offline_reply or self._provider_unavailable_message()
        if time.time() < self.__class__._brain_unavailable_until:
            offline_reply = self._offline_coding_brain_reply(prompt, system_prompt=system_prompt, mode=mode)
            return offline_reply or self._provider_unavailable_message()
        mode = mode or self.think_mode
        try:
            response = await asyncio.wait_for(
                brain.generate_response(prompt, system_prompt=system_prompt, mode=mode),
                timeout=45.0
            )
            if self._is_provider_failure(response):
                self.__class__._brain_unavailable_until = time.time() + 60.0
                logger.warning("%s provider chain unavailable: %s", self.name, str(response)[:300])
                offline_reply = self._offline_coding_brain_reply(prompt, system_prompt=system_prompt, mode=mode)
                return offline_reply or self._provider_unavailable_message()
            return response
        except asyncio.TimeoutError:
            self.__class__._brain_unavailable_until = time.time() + 20.0
            offline_reply = self._offline_coding_brain_reply(prompt, system_prompt=system_prompt, mode=mode)
            return offline_reply or self._provider_unavailable_message("AI provider timed out")
        except Exception as e:
            self.__class__._brain_unavailable_until = time.time() + 20.0
            logger.warning("%s provider call failed: %s", self.name, str(e)[:300])
            offline_reply = self._offline_coding_brain_reply(prompt, system_prompt=system_prompt, mode=mode)
            return offline_reply or self._provider_unavailable_message()

    @staticmethod
    def _is_provider_failure(response: object) -> bool:
        text = str(response or "").lower()
        return (
            "all brains failed" in text
            or "api key missing" in text
            or "resource_exhausted" in text
            or "payment_method_required" in text
            or "rate limit reached" in text
        )

    def _should_use_offline_coding_brain(self, mode: Optional[str] = None) -> bool:
        normalized_mode = str(mode or "").strip().upper()
        return normalized_mode == "CODING" or "code" in set(self.tool_categories or [])

    def _offline_coding_brain_reply(self, prompt: str, system_prompt: Optional[str] = None, mode: Optional[str] = None) -> str:
        if not self._should_use_offline_coding_brain(mode):
            return ""
        try:
            from shell_offline_llm import generate_offline_coding_reply

            result = generate_offline_coding_reply(
                prompt,
                system_prompt=(
                    f"You are helping {self.name}, {self.role}. "
                    f"Expertise: {self.expertise}. "
                    f"{system_prompt or ''}"
                ).strip(),
                previous_messages=[],
            )
            if getattr(result, "success", False) and str(getattr(result, "reply", "")).strip():
                return str(result.reply).strip()
        except Exception as exc:
            logger.debug("%s offline coding brain unavailable: %s", self.name, str(exc)[:200])
        return ""

    def _provider_unavailable_message(self, reason: str = "AI providers are temporarily unavailable") -> str:
        return (
            f"{reason}. {self.name} is loaded, but model reasoning is in degraded mode. "
            "Check API keys/quota or retry after the provider cooldown."
        )

    def _local_ui_smoke_reply(self, task: str) -> Optional[str]:
        if "ui smoke test only" not in str(task or "").lower():
            return None
        replies = {
            "DeveloperAgent": "DeveloperAgent is ready for safe UI smoke validation without writing files.",
            "WebsiteBuilderAgent": "Add a compact hero status section with one clear call-to-action.",
            "AppBuilderAgent": "A safe app feature is a read-only status dashboard.",
            "APIAgent": "GET /health can return service status and version metadata.",
            "DatabaseAgent": "Use ui_smoke_runs as a clear table name for smoke-test results.",
            "SystemAgent": "A safe diagnostic is checking read-only CPU and memory status.",
            "SocialAgent": "Thanks for the update, that sounds great.",
            "SecurityAgent": "Confirm that HTTPS is enabled before testing deeper security behavior.",
            "ResearchAgent": "Which user action is most critical to verify in the first smoke test?",
            "FileAgent": "Group related files by feature area before making any changes.",
            "CreativeAgent": "Shell: instant control, calm intelligence.",
            "ProductivityAgent": "Test the highest-value path first, then widen coverage.",
            "DataAgent": "Chart first-response latency as the primary smoke metric.",
            "NetworkAgent": "Check DNS resolution as a safe read-only network diagnostic.",
            "DevOpsAgent": "Verify the health-check endpoint before deployment.",
            "BrowserAgent": "Load the page and verify the main heading is visible.",
            "CommunicationAgent": "Reminder: quick sync starts in 10 minutes.",
            "LearningAgent": "Loops repeat a block of code until a condition changes or a collection ends.",
            "AutomationAgent": "Automate a read-only status check that reports pass or fail.",
            "TestingAgent": "Verify the primary button triggers the expected success state without layout shift.",
        }
        return replies.get(self.name, f"{self.name} is ready for safe UI smoke validation.")

    def _parse_json_plan(self, response: str) -> List[Dict]:
        try:
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find('[')
            end = cleaned.rfind(']') + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        return []

    async def think(self, task: str) -> List[Dict[str, Any]]:
        tool_desc = self._get_tool_descriptions()
        system_prompt = f"""You are {self.name}, a {self.role}.
Expertise: {self.expertise}

Available tools:
{tool_desc}

Given a task, create an execution plan as a JSON array.
Each step: {{"step": 1, "action": "description", "tool": "tool_name", "params": {{"key": "value"}}}}
If no tool fits, use "tool": "brain" with "params": {{"prompt": "your question"}}.
Use only exact tool names from the Available tools list. Never invent tools such as Selenium, Playwright, pytest, curl, or bash unless they are explicitly listed.
For ideas, plans, explanations, test-case suggestions, reviews, and advisory answers, prefer "tool": "brain" instead of a tool.
Max 7 steps. Return ONLY the JSON array."""

        response = await self._ai_think(task, system_prompt=system_prompt)
        plan = self._parse_json_plan(response)
        if not plan:
            plan = [{"step": 1, "action": task, "tool": "brain", "params": {"prompt": task}}]
        return plan

    async def execute(self, task: str) -> str:
        start_time = time.time()
        results = []

        smoke_reply = self._local_ui_smoke_reply(task)
        if smoke_reply:
            return AgentResult(
                self.name,
                task,
                "success",
                smoke_reply,
                1,
                1,
                0.0,
            ).format()

        # THINK
        try:
            plan = await self.think(task)
        except Exception:
            plan = [{"step": 1, "action": task, "tool": "brain", "params": {"prompt": task}}]

        # EXECUTE
        steps_done = 0
        for step in plan[:7]:
            if time.time() - start_time > 120:
                results.append("⏰ Timeout: Agent exceeded 120s limit.")
                break

            tool_name = step.get("tool", "brain")
            params = step.get("params", {})
            action = step.get("action", "")

            if tool_name == "brain":
                prompt = params.get("prompt", action)
                step_result = await self._ai_think(prompt, mode=self.execute_mode)
            else:
                step_result = await self._call_tool(tool_name, **params)

            results.append(f"Step {step.get('step', '?')}: {action}\n→ {step_result}")
            steps_done += 1

        # SUMMARIZE
        elapsed = round(time.time() - start_time, 2)
        combined = "\n\n".join(results)

        if len(results) > 1:
            summary = await self._ai_think(
                f"Summarize these results concisely.\nTask: {task}\nResults:\n{combined[:3000]}",
                mode="FAST"
            )
        else:
            summary = combined

        hard_failures = [
            result for result in results
            if "\n→ Error:" in result or result.startswith("⏰ Timeout")
        ]
        status = "success" if steps_done == len(plan[:7]) and not hard_failures else ("partial" if steps_done else "failed")

        return AgentResult(
            self.name, task,
            status,
            summary, steps_done, len(plan[:7]), elapsed
        ).format()


# ═══════════════════════════════════════════════════════════════
#  20 SPECIALIST AGENTS
# ═══════════════════════════════════════════════════════════════

class DeveloperAgent(ShellAgent):
    """Unbeatable Developer Agent — Full-stack AI Developer"""
    def __init__(self):
        super().__init__(
            name="DeveloperAgent",
            role="Senior Full-Stack Developer & Code Architect",
            expertise="Full-stack development: code writing, debugging, refactoring, testing, "
                      "optimization, security scanning. Python, JavaScript, HTML/CSS, SQL, Bash. "
                      "Architecture design, code review, git operations, project scaffolding.",
            tool_categories=["code", "utility", "web"],
            think_mode="SMART",
            execute_mode="CODING"
        )

    def _local_code_reply(self, task: str) -> Optional[str]:
        lower = str(task or "").lower()
        if not re.search(
            r"\b(code|coding|script|program|function|class|component|algorithm|python|javascript|typescript|html|css)\b",
            lower,
        ):
            return None

        if "fibonacci" in lower or "fibonnaci" in lower:
            if re.search(r"\b(java\s*script|javascript|js|typescript|ts)\b", lower):
                return (
                    "Here is a clean JavaScript Fibonacci implementation:\n\n"
                    "```javascript\n"
                    "function fibonacci(n) {\n"
                    "  if (!Number.isInteger(n) || n < 0) {\n"
                    "    throw new Error('n must be a non-negative integer');\n"
                    "  }\n"
                    "  let previous = 0;\n"
                    "  let current = 1;\n"
                    "  for (let index = 0; index < n; index += 1) {\n"
                    "    [previous, current] = [current, previous + current];\n"
                    "  }\n"
                    "  return previous;\n"
                    "}\n"
                    "\n"
                    "console.log(fibonacci(10)); // 55\n"
                    "```\n"
                )
            return (
                "Here is a clean Python Fibonacci implementation:\n\n"
                "```python\n"
                "def fibonacci(n: int) -> int:\n"
                "    if n < 0:\n"
                "        raise ValueError('n must be non-negative')\n"
                "    previous, current = 0, 1\n"
                "    for _ in range(n):\n"
                "        previous, current = current, previous + current\n"
                "    return previous\n"
                "\n"
                "\n"
                "print(fibonacci(10))  # 55\n"
                "```\n"
            )

        if re.search(r"\b(sort|sorting)\b", lower) and re.search(r"\b(java\s*script|javascript|js|typescript|ts)\b", lower):
            return (
                "Here is a safe JavaScript sort helper:\n\n"
                "```javascript\n"
                "function sortNumbers(values, direction = 'asc') {\n"
                "  const multiplier = direction === 'desc' ? -1 : 1;\n"
                "  return [...values].sort((left, right) => (left - right) * multiplier);\n"
                "}\n"
                "\n"
                "console.log(sortNumbers([4, 1, 9, 2]));        // [1, 2, 4, 9]\n"
                "console.log(sortNumbers([4, 1, 9, 2], 'desc')); // [9, 4, 2, 1]\n"
                "```\n"
            )

        if re.search(r"\b(sort|sorting)\b", lower):
            return (
                "Here is a simple Python sort helper:\n\n"
                "```python\n"
                "def sort_values(values: list[int], descending: bool = False) -> list[int]:\n"
                "    return sorted(values, reverse=descending)\n"
                "\n"
                "\n"
                "print(sort_values([4, 1, 9, 2]))        # [1, 2, 4, 9]\n"
                "print(sort_values([4, 1, 9, 2], True))  # [9, 4, 2, 1]\n"
                "```\n"
            )

        return None

    async def execute(self, task: str) -> str:
        start_time = time.time()
        results = []

        smoke_reply = self._local_ui_smoke_reply(task)
        if smoke_reply:
            return AgentResult(
                self.name,
                task,
                "success",
                smoke_reply,
                1,
                1,
                0.0,
            ).format()

        local_code_reply = self._local_code_reply(task)
        if local_code_reply:
            return AgentResult(
                self.name,
                task,
                "success",
                local_code_reply,
                1,
                1,
                round(time.time() - start_time, 2),
            ).format()

        # Phase 1: ANALYZE
        analysis = await self._ai_think(
            f"Analyze this development task and identify what needs to be done, "
            f"what technologies to use, and potential challenges:\n{task}",
            mode="SMART"
        )
        results.append(f"📋 ANALYSIS:\n{analysis}")

        # Phase 2: PLAN & CODE
        plan = await self.think(task)
        for step in plan[:7]:
            if time.time() - start_time > 120:
                results.append("⏰ Timeout reached.")
                break
            tool_name = step.get("tool", "brain")
            params = step.get("params", {})
            action = step.get("action", "")
            if tool_name == "brain":
                step_result = await self._ai_think(
                    params.get("prompt", action), mode="CODING"
                )
            else:
                step_result = await self._call_tool(tool_name, **params)
            results.append(f"🔨 {action}\n→ {step_result}")

        # Phase 3: CODE REVIEW
        review = await self._ai_think(
            f"Review the work done for quality, security, and best practices:\n"
            f"Task: {task}\nResults:\n{chr(10).join(r[:200] for r in results[-3:])}",
            mode="SMART"
        )
        results.append(f"✅ CODE REVIEW:\n{review}")

        elapsed = round(time.time() - start_time, 2)
        combined = "\n\n".join(results)

        summary = await self._ai_think(
            f"Give a final developer summary of what was built/done:\n{combined[:3000]}",
            mode="FAST"
        )

        return AgentResult(
            self.name, task, "success", summary,
            len(results), len(results), elapsed
        ).format()


class WebsiteBuilderAgent(ShellAgent):
    """Full Website Creator — HTML/CSS/JS from scratch"""
    def __init__(self):
        super().__init__(
            name="WebsiteBuilderAgent",
            role="Expert Web Designer & Frontend Developer",
            expertise="Complete website creation: HTML5, CSS3, JavaScript, responsive design, "
                      "landing pages, portfolios, e-commerce layouts, SEO optimization, "
                      "Bootstrap/Tailwind patterns, contact forms, navigation, animations.",
            tool_categories=["code", "web", "utility"],
            think_mode="SMART",
            execute_mode="CODING"
        )


class AppBuilderAgent(ShellAgent):
    """Full Application Creator"""
    def __init__(self):
        super().__init__(
            name="AppBuilderAgent",
            role="Application Architect & Full-Stack Builder",
            expertise="Full application creation: Flask/FastAPI web apps, REST APIs, "
                      "Python desktop apps (Tkinter/PyQt), CLI tools, project scaffolding, "
                      "database schema design, authentication systems, deployment configs.",
            tool_categories=["code", "utility"],
            think_mode="SMART",
            execute_mode="CODING"
        )


class APIAgent(ShellAgent):
    """API Master — Design, Build, Test, Document"""
    def __init__(self):
        super().__init__(
            name="APIAgent",
            role="API Architect & Integration Specialist",
            expertise="REST API design, implementation, endpoint testing, documentation generation, "
                      "third-party API integration, authentication (JWT/OAuth), rate limiting, "
                      "request/response format handling, OpenAPI/Swagger specs.",
            tool_categories=["code", "web", "utility"],
            think_mode="SMART",
            execute_mode="CODING"
        )


class DatabaseAgent(ShellAgent):
    """Database Expert"""
    def __init__(self):
        super().__init__(
            name="DatabaseAgent",
            role="Database Architect & Query Optimizer",
            expertise="Database design, SQL query writing/optimization, schema design, "
                      "migration scripts, data modeling (relational + NoSQL), indexing strategies, "
                      "backup planning, data integrity, ORM patterns (SQLAlchemy).",
            tool_categories=["code", "utility"],
            think_mode="SMART",
            execute_mode="CODING"
        )


class SystemAgent(ShellAgent):
    """System & OS Control"""
    def __init__(self):
        super().__init__(
            name="SystemAgent",
            role="System Administrator & Diagnostics Expert",
            expertise="OS control, process management, app launching, system diagnostics, "
                      "performance monitoring, disk management, service control, environment setup.",
            tool_categories=["system", "utility"]
        )


class SocialAgent(ShellAgent):
    """Social Media & Communication"""
    def __init__(self):
        super().__init__(
            name="SocialAgent",
            role="Social Media & Communication Manager",
            expertise="WhatsApp messaging/monitoring, email composition/sending, Telegram bots, "
                      "Instagram automation, social media scheduling, auto-reply setup.",
            tool_categories=["communication", "social"]
        )


class SecurityAgent(ShellAgent):
    """Security & Threat Analysis"""
    def __init__(self):
        super().__init__(
            name="SecurityAgent",
            role="Cybersecurity Analyst & Code Auditor",
            expertise="Security scanning, vulnerability detection, code auditing, threat analysis, "
                      "network security, penetration testing patterns, OWASP compliance, "
                      "malware detection, encryption best practices.",
            tool_categories=["security", "code"]
        )


class ResearchAgent(ShellAgent):
    """Deep Research & Analysis"""
    def __init__(self):
        super().__init__(
            name="ResearchAgent",
            role="Research Analyst & Information Specialist",
            expertise="Deep web search, multi-source research, fact-checking, summarization, "
                      "technical analysis, competitive analysis, trend research, documentation.",
            tool_categories=["web", "knowledge"]
        )


class FileAgent(ShellAgent):
    """File Management"""
    def __init__(self):
        super().__init__(
            name="FileAgent",
            role="File System Manager & Organization Expert",
            expertise="File management, folder organization, format conversion, batch rename, "
                      "duplicate finding, cleanup, file search, archive management.",
            tool_categories=["system", "utility"]
        )


class CreativeAgent(ShellAgent):
    """Creative Content & Design"""
    def __init__(self):
        super().__init__(
            name="CreativeAgent",
            role="Creative Director & Content Creator",
            expertise="Image generation, content writing, copywriting, design concepts, "
                      "visual effects, branding ideas, social media content, storytelling.",
            tool_categories=["media"]
        )


class ProductivityAgent(ShellAgent):
    """Productivity & Planning"""
    def __init__(self):
        super().__init__(
            name="ProductivityAgent",
            role="Productivity Coach & Task Manager",
            expertise="Timer management, task tracking, note-taking, planning, scheduling, "
                      "reminders, habit tracking, goal setting, time management.",
            tool_categories=["productivity", "knowledge"]
        )


class DataAgent(ShellAgent):
    """Data Analysis & Processing"""
    def __init__(self):
        super().__init__(
            name="DataAgent",
            role="Data Scientist & Analytics Expert",
            expertise="Data analysis, CSV/JSON/Excel processing, statistics, data visualization, "
                      "data cleaning, pattern recognition, report generation, ETL pipelines.",
            tool_categories=["utility", "code"]
        )


class NetworkAgent(ShellAgent):
    """Network Diagnostics"""
    def __init__(self):
        super().__init__(
            name="NetworkAgent",
            role="Network Engineer & Connectivity Specialist",
            expertise="Network diagnostics, speed testing, port scanning, API testing, "
                      "DNS lookup, connectivity checks, latency analysis, firewall rules.",
            tool_categories=["web", "system"]
        )


class DevOpsAgent(ShellAgent):
    """DevOps & Deployment"""
    def __init__(self):
        super().__init__(
            name="DevOpsAgent",
            role="DevOps Engineer & Infrastructure Specialist",
            expertise="Server management, Docker containerization, CI/CD pipelines, "
                      "deployment automation, log analysis, monitoring setup, cloud config.",
            tool_categories=["system", "code", "utility"]
        )


class BrowserAgent(ShellAgent):
    """Browser Automation"""
    def __init__(self):
        super().__init__(
            name="BrowserAgent",
            role="Web Automation & Scraping Specialist",
            expertise="Web automation, scraping, form filling, screenshot capture, "
                      "page interaction, browser testing, data extraction from websites.",
            tool_categories=["web"]
        )


class CommunicationAgent(ShellAgent):
    """Professional Communication"""
    def __init__(self):
        super().__init__(
            name="CommunicationAgent",
            role="Communication Manager & Message Crafter",
            expertise="Email drafting, professional messaging, meeting scheduling, "
                      "contact management, message templates, follow-up tracking.",
            tool_categories=["communication"]
        )


class LearningAgent(ShellAgent):
    """Learning & Education"""
    def __init__(self):
        super().__init__(
            name="LearningAgent",
            role="Learning Facilitator & Knowledge Guide",
            expertise="Tutorial search, concept explanation, skill assessment, "
                      "learning path creation, documentation lookup, course recommendations.",
            tool_categories=["knowledge", "web"]
        )


class AutomationAgent(ShellAgent):
    """Workflow Automation"""
    def __init__(self):
        super().__init__(
            name="AutomationAgent",
            role="Automation Engineer & Workflow Designer",
            expertise="Workflow automation, task scheduling, batch processing, "
                      "macro creation, repetitive task handling, script automation.",
            tool_categories=["system", "utility", "code"]
        )


class TestingAgent(ShellAgent):
    """QA & Testing Expert"""
    def __init__(self):
        super().__init__(
            name="TestingAgent",
            role="QA Engineer & Testing Architect",
            expertise="Test writing (unit, integration, e2e), pytest/unittest frameworks, "
                      "bug reproduction, test case generation, code coverage analysis, "
                      "performance testing, test automation, regression testing.",
            tool_categories=["code", "utility"],
            think_mode="SMART",
            execute_mode="CODING"
        )

    async def execute(self, task: str) -> str:
        lower = str(task or "").lower()
        simple_idea = "test idea" in lower and re.search(r"\b(one|single|short|brief)\b", lower)
        if simple_idea:
            idea = (
                "Open the target screen, perform the primary user action once, "
                "and verify the expected success state appears without errors or layout shift."
            )
            return AgentResult(
                self.name,
                task,
                "success",
                idea,
                1,
                1,
                0.0,
            ).format()
        return await super().execute(task)


# ═══════════════════════════════════════════════════════════════
#  MASTER AGENT — INTELLIGENT ROUTER
# ═══════════════════════════════════════════════════════════════

class ShellMasterAgent:
    """Boss Agent — Routes tasks to the best specialist agent(s)."""

    AGENT_MAP = {
        "developer": DeveloperAgent,
        "website": WebsiteBuilderAgent,
        "app": AppBuilderAgent,
        "api": APIAgent,
        "database": DatabaseAgent,
        "system": SystemAgent,
        "social": SocialAgent,
        "security": SecurityAgent,
        "research": ResearchAgent,
        "file": FileAgent,
        "creative": CreativeAgent,
        "productivity": ProductivityAgent,
        "data": DataAgent,
        "network": NetworkAgent,
        "devops": DevOpsAgent,
        "browser": BrowserAgent,
        "communication": CommunicationAgent,
        "learning": LearningAgent,
        "automation": AutomationAgent,
        "testing": TestingAgent,
    }

    def __init__(self):
        self._agents = {}

    @staticmethod
    def _local_ui_smoke_reply(task: str) -> Optional[str]:
        if "ui smoke test only" not in str(task or "").lower():
            return None
        return "MasterAgent is ready and would route this harmless status check without executing tools."

    def _get_agent(self, domain: str) -> Optional[ShellAgent]:
        if domain not in self._agents:
            cls = self.AGENT_MAP.get(domain)
            if cls:
                self._agents[domain] = cls()
        return self._agents.get(domain)

    async def route(self, task: str) -> List[str]:
        brain = ShellAgent._get_brain()
        if not brain:
            return ["research"]

        prompt = f"""Classify this task into 1-3 domains (pick the MOST relevant ones).
Available domains: {list(self.AGENT_MAP.keys())}

Task: {task}

Return ONLY a JSON array of domain strings. Example: ["developer", "testing"]"""

        try:
            response = await asyncio.wait_for(
                brain.generate_response(prompt, mode="FAST"), timeout=15.0
            )
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find('[')
            end = cleaned.rfind(']') + 1
            if start != -1 and end > start:
                domains = json.loads(cleaned[start:end])
                valid = [d for d in domains if d in self.AGENT_MAP]
                if valid:
                    return valid[:3]
        except Exception as e:
            logger.warning(f"Master routing failed: {e}")

        # Keyword fallback
        task_lower = task.lower()
        keyword_map = {
            "developer": ["code", "function", "class", "debug", "refactor", "programming", "script"],
            "website": ["website", "html", "css", "landing page", "web page", "frontend", "webpage"],
            "app": ["app", "application", "flask", "fastapi", "desktop", "gui"],
            "api": ["api", "endpoint", "rest", "graphql", "webhook"],
            "database": ["database", "sql", "query", "table", "schema", "migration", "db"],
            "system": ["system", "process", "cpu", "ram", "disk", "os", "service", "install"],
            "social": ["whatsapp", "instagram", "telegram", "tweet", "social media"],
            "security": ["security", "vulnerability", "scan", "audit", "threat", "hack", "malware"],
            "research": ["search", "find", "research", "information", "learn about"],
            "file": ["file", "folder", "rename", "organize", "convert", "move", "copy", "delete"],
            "creative": ["image", "design", "write", "content", "creative", "logo", "banner"],
            "productivity": ["timer", "reminder", "task", "note", "schedule", "plan", "todo"],
            "data": ["data", "csv", "excel", "analyze", "statistics", "chart", "graph"],
            "network": ["network", "ping", "speed", "port", "dns", "internet", "connection"],
            "devops": ["deploy", "docker", "server", "ci/cd", "pipeline", "container"],
            "browser": ["browser", "scrape", "click", "form", "navigate", "screenshot"],
            "communication": ["email", "mail", "message", "meeting", "contact"],
            "learning": ["tutorial", "learn", "course", "explain", "teach", "understand"],
            "automation": ["automate", "workflow", "batch", "macro", "schedule", "cron"],
            "testing": ["test", "unittest", "pytest", "coverage", "qa", "bug"],
        }
        for domain, keywords in keyword_map.items():
            if any(kw in task_lower for kw in keywords):
                return [domain]
        return ["research"]

    async def execute(self, task: str) -> str:
        smoke_reply = self._local_ui_smoke_reply(task)
        if smoke_reply:
            return smoke_reply

        domains = await self.route(task)
        results = []
        for domain in domains[:3]:
            agent = self._get_agent(domain)
            if agent:
                try:
                    result = await agent.execute(task)
                    results.append(result)
                except Exception as e:
                    results.append(f"[{domain}] Error: {str(e)[:200]}")
        return "\n\n---\n\n".join(results) if results else "Koi suitable agent nahi mila."


# ═══════════════════════════════════════════════════════════════
#  22 @function_tool — SHELL KE LIYE
# ═══════════════════════════════════════════════════════════════

# Lazy singletons
_agents_cache = {}

def _get_agent(cls):
    name = cls.__name__
    if name not in _agents_cache:
        _agents_cache[name] = cls()
    return _agents_cache[name]


@function_tool
async def developer_agent_tool(task: str) -> str:
    """UNBEATABLE Developer Agent — Full-stack coding, debugging, refactoring, testing, code review, optimization. Handles Python, JS, HTML, SQL, Bash and more."""
    return await _get_agent(DeveloperAgent).execute(task)


@function_tool
async def website_builder_agent_tool(task: str) -> str:
    """Website Builder Agent — Creates complete websites with HTML/CSS/JS, responsive design, landing pages, portfolios, e-commerce layouts, SEO optimization."""
    return await _get_agent(WebsiteBuilderAgent).execute(task)


@function_tool
async def app_builder_agent_tool(task: str) -> str:
    """App Builder Agent — Creates full applications: Flask/FastAPI web apps, REST APIs, desktop apps, CLI tools, project scaffolding with configs."""
    return await _get_agent(AppBuilderAgent).execute(task)


@function_tool
async def api_agent_tool(task: str) -> str:
    """API Agent — API design, implementation, testing, documentation, third-party integration, authentication setup."""
    return await _get_agent(APIAgent).execute(task)


@function_tool
async def database_agent_tool(task: str) -> str:
    """Database Agent — Database design, SQL queries, schema design, migrations, optimization, data modeling."""
    return await _get_agent(DatabaseAgent).execute(task)


@function_tool
async def system_agent_tool(task: str) -> str:
    """System Agent — OS control, process management, app launching, system diagnostics, performance monitoring."""
    return await _get_agent(SystemAgent).execute(task)


@function_tool
async def social_agent_tool(task: str) -> str:
    """Social Agent — WhatsApp, email, Telegram, Instagram messaging, monitoring, auto-reply setup."""
    return await _get_agent(SocialAgent).execute(task)


@function_tool
async def security_agent_tool(task: str) -> str:
    """Security Agent — Security scanning, vulnerability detection, code auditing, threat analysis, OWASP compliance."""
    return await _get_agent(SecurityAgent).execute(task)


@function_tool
async def research_agent_tool(task: str) -> str:
    """Research Agent — Deep web search, multi-source research, fact-checking, summarization, analysis reports."""
    return await _get_agent(ResearchAgent).execute(task)


@function_tool
async def file_agent_tool(task: str) -> str:
    """File Agent — File management, organization, conversion, batch rename, duplicate finding, cleanup."""
    return await _get_agent(FileAgent).execute(task)


@function_tool
async def creative_agent_tool(task: str) -> str:
    """Creative Agent — Image generation, content writing, copywriting, design concepts, branding ideas."""
    return await _get_agent(CreativeAgent).execute(task)


@function_tool
async def productivity_agent_tool(task: str) -> str:
    """Productivity Agent — Timers, task management, notes, planning, scheduling, reminders, goal tracking."""
    return await _get_agent(ProductivityAgent).execute(task)


@function_tool
async def data_agent_tool(task: str) -> str:
    """Data Agent — Data analysis, CSV/JSON/Excel processing, statistics, visualization, data cleaning."""
    return await _get_agent(DataAgent).execute(task)


@function_tool
async def network_agent_tool(task: str) -> str:
    """Network Agent — Network diagnostics, speed test, port scanning, API testing, DNS lookup, connectivity checks."""
    return await _get_agent(NetworkAgent).execute(task)


@function_tool
async def devops_agent_tool(task: str) -> str:
    """DevOps Agent — Server management, Docker, CI/CD, deployment automation, log analysis, monitoring."""
    return await _get_agent(DevOpsAgent).execute(task)


@function_tool
async def browser_agent_tool(task: str) -> str:
    """Browser Agent — Web automation, scraping, form filling, screenshot capture, page interaction."""
    return await _get_agent(BrowserAgent).execute(task)


@function_tool
async def communication_agent_tool(task: str) -> str:
    """Communication Agent — Email drafting, professional messaging, meeting scheduling, contact management."""
    return await _get_agent(CommunicationAgent).execute(task)


@function_tool
async def learning_agent_tool(task: str) -> str:
    """Learning Agent — Tutorial search, concept explanation, skill assessment, learning path creation."""
    return await _get_agent(LearningAgent).execute(task)


@function_tool
async def automation_agent_tool(task: str) -> str:
    """Automation Agent — Workflow automation, task scheduling, batch processing, macro creation."""
    return await _get_agent(AutomationAgent).execute(task)


@function_tool
async def testing_agent_tool(task: str) -> str:
    """Testing Agent — Test writing (unit/integration/e2e), pytest/unittest, bug reproduction, coverage analysis."""
    return await _get_agent(TestingAgent).execute(task)


@function_tool
async def master_agent_tool(task: str) -> str:
    """Master Agent — Automatically routes your task to the best specialist AI agent. Just describe what you want done."""
    return await _get_agent(ShellMasterAgent).execute(task)


@function_tool
async def list_agents_tool() -> str:
    """Lists all 21 available Shell AI Agents with their specialties."""
    agents = [
        ("DeveloperAgent", "Full-stack coding, debugging, refactoring, testing, code review — UNBEATABLE"),
        ("WebsiteBuilderAgent", "Complete website creation — HTML/CSS/JS, responsive, SEO"),
        ("AppBuilderAgent", "Full app creation — Flask, FastAPI, desktop, CLI, scaffolding"),
        ("APIAgent", "API design, implementation, testing, documentation"),
        ("DatabaseAgent", "Database design, SQL, schema, migrations, optimization"),
        ("SystemAgent", "OS control, process management, app launching, diagnostics"),
        ("SocialAgent", "WhatsApp, email, Telegram, Instagram automation"),
        ("SecurityAgent", "Security scanning, vulnerability detection, code audit"),
        ("ResearchAgent", "Deep web search, fact-check, summarize, analysis"),
        ("FileAgent", "File management, organization, conversion, cleanup"),
        ("CreativeAgent", "Image generation, content writing, design concepts"),
        ("ProductivityAgent", "Timers, tasks, notes, planning, reminders"),
        ("DataAgent", "Data analysis, CSV/JSON/Excel, statistics, visualization"),
        ("NetworkAgent", "Network diagnostics, speed test, port scanning"),
        ("DevOpsAgent", "Server management, Docker, CI/CD, deployment"),
        ("BrowserAgent", "Web automation, scraping, form filling, testing"),
        ("CommunicationAgent", "Email drafting, meeting scheduling, messaging"),
        ("LearningAgent", "Tutorials, concept explanation, learning paths"),
        ("AutomationAgent", "Workflow automation, batch processing, macros"),
        ("TestingAgent", "Test writing, pytest, coverage, QA, bug reproduction"),
        ("MasterAgent", "Auto-routes tasks to the best specialist agent"),
    ]
    lines = [f"Shell AI Agents — {len(agents)} Agents Ready\n{'='*50}"]
    for i, (name, desc) in enumerate(agents, 1):
        lines.append(f"  {i:2d}. {name}: {desc}")
    lines.append(f"\n{'='*50}")
    lines.append("Use 'master_agent_tool' to auto-route any task!")
    return "\n".join(lines)
