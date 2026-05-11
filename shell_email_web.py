#!/usr/bin/env python3
"""
Gmail Web automation fallback for email sending.

Use this when SMTP is unavailable (for example Gmail app-password not configured).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.parse
from datetime import datetime
from typing import Dict, Optional, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from shell_safe_executor import god_tier_tool as function_tool
except ImportError:
    def function_tool(func):
        return func

from shell_email_tool import (
    _clean_email,
    _discover_company_email,
    _generate_professional_body,
    _generate_subject,
    _is_probably_valid_email,
    _sanitize_text,
)

from shell_config import config
from shell_logger import get_logger

logger = get_logger("gmail_web_mailer")


class GmailWebMailer:
    """Automates Gmail web compose and send using Selenium Chrome driver."""

    def __init__(self) -> None:
        self.driver = None
        self._session_start_time: Optional[float] = None

    def _get_profile_dir(self) -> str:
        """Returns the resolved profile directory path."""
        profile_dir = config.get_str("SHELL_GMAIL_WEB_PROFILE_DIR", "~/.shell_gmail_chrome")
        return os.path.expanduser(profile_dir)

    def _chrome_options(self, headless: bool = False) -> Options:
        options = Options()
        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1600,1000")

        profile_dir = self._get_profile_dir()
        os.makedirs(profile_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={profile_dir}")

        return options

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
            self.driver = None
            self._session_start_time = None

    def _is_logged_in(self) -> bool:
        if self.driver is None:
            return False
        current = (self.driver.current_url or "").lower()
        return "mail.google.com" in current and "accounts.google.com" not in current

    def start_session(self, headless: bool = False) -> Tuple[bool, str]:
        """Starts browser and opens Gmail. Returns login state guidance."""
        try:
            if self.driver is not None:
                try:
                    _ = self.driver.title
                except Exception:
                    self.close()

            if self.driver is None:
                self.driver = webdriver.Chrome(options=self._chrome_options(headless=headless))
                self._session_start_time = time.time()

            self.driver.get("https://mail.google.com/")
            time.sleep(2.0)

            if not self._is_logged_in():
                return True, "Gmail login required in opened browser window. Please sign in once, then retry send."

            return True, "Gmail Web session ready."
        except Exception as exc:
            logger.error("Gmail session start failed: %s", exc)
            self.close()
            return False, f"Failed to launch Gmail Web: {exc}"

    def _build_compose_url(
        self,
        recipient: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
    ) -> str:
        params = {
            "view": "cm",
            "fs": "1",
            "tf": "1",
            "to": recipient,
            "su": subject,
            "body": body,
        }
        if cc.strip():
            params["cc"] = cc.strip()
        if bcc.strip():
            params["bcc"] = bcc.strip()

        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        return f"https://mail.google.com/mail/u/0/?{query}"

    def send_mail(
        self,
        recipient: str,
        subject: str,
        body: str,
        cc: str = "",
        bcc: str = "",
        auto_send: bool = True,
        headless: bool = False,
    ) -> Tuple[bool, str]:
        """Opens Gmail compose with prefilled fields and optionally clicks Send."""
        ok, msg = self.start_session(headless=headless)
        if not ok:
            return False, msg

        recipient_clean = _clean_email(recipient)
        if not _is_probably_valid_email(recipient_clean):
            return False, f"Invalid recipient email: {recipient}"

        compose_url = self._build_compose_url(
            recipient=recipient_clean,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
        )

        self.driver.get(compose_url)
        time.sleep(2.2)

        if not self._is_logged_in():
            return False, "Gmail login required. Please log in to Gmail Web and run command again."

        if not auto_send:
            return True, f"Compose window opened for {recipient_clean}. Please review and click Send manually."

        # Try multiple selectors because Gmail UI can vary slightly by account/locale.
        send_selectors = [
            (By.CSS_SELECTOR, 'div[role="button"][data-tooltip*="Ctrl-Enter"]'),
            (By.CSS_SELECTOR, 'div[role="button"][aria-label*="Send"]'),
            (By.CSS_SELECTOR, 'div[role="button"][data-tooltip^="Send"]'),
            (By.XPATH, '//div[@role="button" and contains(@aria-label, "Send")]'),
            (By.XPATH, '//div[@role="button" and .//span[text()="Send"]]'),
        ]

        for by, selector in send_selectors:
            try:
                send_button = WebDriverWait(self.driver, 7).until(
                    EC.element_to_be_clickable((by, selector))
                )
                send_button.click()
                time.sleep(1.2)
                return True, f"Email sent via Gmail Web to {recipient_clean}."
            except Exception:
                continue

        # Keyboard fallback: focus message body and use Ctrl+Enter.
        try:
            body_box = WebDriverWait(self.driver, 7).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[aria-label="Message Body"]'))
            )
            body_box.send_keys(Keys.CONTROL, Keys.ENTER)
            time.sleep(1.2)
            return True, f"Email sent via Gmail Web (keyboard fallback) to {recipient_clean}."
        except Exception as exc:
            return False, f"Could not click Send button in Gmail Web: {exc}"


gmail_web_mailer = GmailWebMailer()


@function_tool
async def link_gmail_web_tool(headless: bool = False) -> str:
    """
    Opens Gmail Web in a persistent browser profile so you can log in once.
    Browser profile mein Gmail open karta hai - ek baar login karo, phir automatic kaam karega.
    """
    ok, message = await asyncio.to_thread(gmail_web_mailer.start_session, headless)

    profile_dir = gmail_web_mailer._get_profile_dir()
    browser_running = gmail_web_mailer.driver is not None

    lines = []
    if ok:
        lines.append(f"Gmail Web Link: {message}")
    else:
        lines.append(f"Failed ho gaya bhai: {message}")

    lines.append(f"Profile Directory: {profile_dir}")
    lines.append(f"Browser Status: {'Running - chal raha hai' if browser_running else 'Not running - band hai'}")

    return "\n".join(lines)


@function_tool
async def send_email_web_tool(
    recipient: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    auto_send: bool = True,
) -> str:
    """
    Sends an email via Gmail Web compose page (browser automation fallback).
    Gmail Web se email bhejta hai - browser automation ke through kaam karta hai.
    """
    # --- Validation: subject aur body empty nahi hona chahiye ---
    if not subject or not subject.strip():
        return "Validation Error: Subject khali hai bhai! Email ka subject dena zaroori hai. Please provide a valid subject."

    if not body or not body.strip():
        return "Validation Error: Body khali hai bhai! Email ka body/message dena zaroori hai. Please provide a valid body."

    if not recipient or not recipient.strip():
        return "Validation Error: Recipient khali hai! Kisko bhejein? Please provide a valid recipient email address."

    ok, message = await asyncio.to_thread(
        gmail_web_mailer.send_mail,
        recipient,
        subject,
        body,
        cc,
        bcc,
        auto_send,
        False,
    )

    subject_chars = len(subject.strip())
    body_chars = len(body.strip())

    lines = []
    if ok:
        lines.append(f"Email bhej diya successfully: {message}")
    else:
        lines.append(f"Email bhejne mein fail ho gaya: {message}")

    lines.append(f"Subject Length: {subject_chars} characters")
    lines.append(f"Body Length: {body_chars} characters")

    return "\n".join(lines)


@function_tool
async def smart_company_email_web_tool(
    company_name: str,
    purpose: str,
    recipient_email: str = "",
    company_website: str = "",
    additional_context: str = "",
    tone: str = "formal",
    custom_subject: str = "",
    cc: str = "",
    bcc: str = "",
    auto_send: bool = True,
) -> str:
    """
    End-to-end browser mode:
    1. Find company email (if missing)
    2. Draft professional subject/body
    3. Send from Gmail Web compose
    """
    company = _sanitize_text(company_name)
    if not company:
        return "Failed: company_name is required."

    purpose_clean = _sanitize_text(purpose)
    if not purpose_clean:
        return "Failed: purpose is required."

    target = _clean_email(recipient_email)
    discovery_meta: Dict[str, str] = {}

    if target and not _is_probably_valid_email(target):
        return f"Failed: invalid recipient_email '{recipient_email}'."

    if not target:
        discovered, meta = await asyncio.to_thread(_discover_company_email, company, company_website)
        discovery_meta = meta
        if not discovered:
            return (
                f"Failed: could not find a safe public email for {company}. "
                "Please provide recipient_email manually."
            )
        target = discovered

    subject = _generate_subject(company, purpose_clean, custom_subject=custom_subject)
    body = _generate_professional_body(
        company_name=company,
        purpose=purpose_clean,
        additional_context=additional_context,
        tone=tone,
    )

    ok, message = await asyncio.to_thread(
        gmail_web_mailer.send_mail,
        target,
        subject,
        body,
        cc,
        bcc,
        auto_send,
        False,
    )

    if not ok:
        return f"Failed: {message}"

    result = {
        "status": "sent" if auto_send else "draft_opened",
        "company": company,
        "recipient": target,
        "subject": subject,
        "delivery": "gmail_web",
        "discovery": discovery_meta,
    }
    return json.dumps(result, ensure_ascii=True)


@function_tool
async def get_gmail_web_session_status_tool() -> str:
    """
    Gmail Web session ka full status dikhata hai - browser, login, profile directory sab kuch.
    Shows Gmail Web session status: browser initialized, logged in, profile directory path/size, session uptime.
    """
    profile_dir = gmail_web_mailer._get_profile_dir()
    browser_initialized = gmail_web_mailer.driver is not None

    # Browser alive check
    browser_alive = False
    if browser_initialized:
        try:
            _ = gmail_web_mailer.driver.title
            browser_alive = True
        except Exception:
            browser_alive = False

    # Login status
    logged_in = False
    if browser_alive:
        try:
            logged_in = gmail_web_mailer._is_logged_in()
        except Exception:
            logged_in = False

    # Profile directory size
    profile_size_str = "N/A"
    if os.path.isdir(profile_dir):
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(profile_dir):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except Exception as _e:
                        logger.debug("ignored Exception: %s", _e)
            if total_size < 1024 * 1024:
                profile_size_str = f"{total_size / 1024:.1f} KB"
            else:
                profile_size_str = f"{total_size / (1024 * 1024):.1f} MB"
        except Exception:
            profile_size_str = "Error calculating size"
    else:
        profile_size_str = "Directory nahi mila - not found"

    # Session uptime
    uptime_str = "No active session"
    if gmail_web_mailer._session_start_time is not None:
        elapsed = time.time() - gmail_web_mailer._session_start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        uptime_str = f"{hours}h {minutes}m {seconds}s"

    lines = [
        "===== Gmail Web Session Status =====",
        f"Browser Initialized: {'Haan (Yes)' if browser_initialized else 'Nahi (No)'}",
        f"Browser Alive: {'Haan - chal raha hai' if browser_alive else 'Nahi - band hai'}",
        f"Gmail Logged In: {'Haan - login hai' if logged_in else 'Nahi - login nahi hai'}",
        f"Profile Directory: {profile_dir}",
        f"Profile Size: {profile_size_str}",
        f"Session Uptime: {uptime_str}",
        "==================================",
    ]

    return "\n".join(lines)
