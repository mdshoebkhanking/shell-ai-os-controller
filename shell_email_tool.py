import re
import ssl
import json
import smtplib
from email.message import EmailMessage
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple

import requests
from shell_safe_executor import god_tier_tool as function_tool
from shell_config import config
from shell_logger import get_logger
from shell_validator import is_valid_email

logger = get_logger("shell_email")

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BLOCKED_LOCAL_PARTS = {"noreply", "no-reply", "donotreply", "do-not-reply"}
PREFERRED_LOCAL_PARTS = {
    "contact",
    "info",
    "hello",
    "support",
    "sales",
    "business",
    "partnership",
    "partnerships",
    "careers",
    "hr",
    "press",
}

HTTP_HEADERS = {
    "User-Agent": "Shell-AI-Email/1.0",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalize_domain(domain: str) -> str:
    cleaned = (domain or "").strip().lower()
    cleaned = cleaned.replace("https://", "").replace("http://", "")
    cleaned = cleaned.split("/")[0]
    if cleaned.startswith("www."):
        cleaned = cleaned[4:]
    return cleaned


def _extract_domain_from_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.netloc or parsed.path
        return _normalize_domain(host)
    except Exception:
        return ""


def _sanitize_text(value: str) -> str:
    return " ".join((value or "").replace("\n", " ").replace("\r", " ").split()).strip()


def _clean_email(raw: str) -> str:
    return raw.strip().strip(".,;:()[]{}<>'\"").lower()


def _is_probably_valid_email(email: str) -> bool:
    addr = _clean_email(email)
    if not EMAIL_REGEX.fullmatch(addr):
        return False
    local_part = addr.split("@", 1)[0]
    if local_part in BLOCKED_LOCAL_PARTS:
        return False
    return True


def _smtp_config() -> Dict[str, str]:
    server = config.get_str("SHELL_SMTP_SERVER", "smtp.gmail.com").strip() or "smtp.gmail.com"
    port = config.get_str("SHELL_SMTP_PORT", "587").strip() or "587"
    return {
        "server": server,
        "port": port,
        "sender_email": config.get_str("SHELL_SENDER_EMAIL", "").strip(),
        "sender_password": config.get_str("SHELL_SENDER_PASSWORD", "").strip(),
        "use_ssl": config.get_str("SHELL_SMTP_USE_SSL", "false").strip().lower(),
    }


def _web_fallback_enabled() -> bool:
    return config.get_str("SHELL_EMAIL_WEB_FALLBACK", "true").strip().lower() in {"1", "true", "yes"}


def _validate_smtp_credentials(config: Dict[str, str]) -> Tuple[bool, str]:
    sender_email = config.get("sender_email", "")
    sender_password = config.get("sender_password", "")

    if not sender_email or not sender_password:
        return False, (
            "SMTP credentials missing. Set SHELL_SENDER_EMAIL and SHELL_SENDER_PASSWORD in .env "
            "(use app password for Gmail)."
        )

    if sender_email == "your_email@gmail.com" or sender_password == "your_password":
        return False, "SMTP placeholders detected. Please set real credentials in .env."

    if not _is_probably_valid_email(sender_email):
        return False, f"Invalid sender email format: {sender_email}"

    return True, "ok"


def _friendly_smtp_error(exc: Exception) -> str:
    text = str(exc)
    lower = text.lower()
    if isinstance(exc, smtplib.SMTPAuthenticationError) or "535" in text or "badcredentials" in lower:
        return (
            "Gmail rejected the SMTP login (535 BadCredentials). Use a Google App Password, "
            "not your normal Gmail password. Enable 2-Step Verification on the sender account, "
            "create an App Password for Mail, then save that 16-character app password as "
            "SHELL_SENDER_PASSWORD. SHELL_SENDER_EMAIL must be the same Gmail account."
        )
    if isinstance(exc, smtplib.SMTPConnectError):
        return f"SMTP connection failed. Check SHELL_SMTP_SERVER and SHELL_SMTP_PORT. Raw error: {text}"
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return f"SMTP server disconnected. Check network/provider availability. Raw error: {text}"
    return text


def _friendly_web_fallback_error(message: str) -> str:
    text = str(message or "")
    if "No module named 'selenium'" in text or 'No module named "selenium"' in text:
        return (
            "Gmail web fallback is unavailable because Selenium is not installed in the active "
            "Shell environment. Run Repair Shell AI or install selenium in the active venv. "
            "SMTP with a Gmail App Password is still the recommended path."
        )
    return text


def _sender_profile() -> Dict[str, str]:
    return {
        "name": config.get_str("SHELL_SENDER_NAME", ""),
        "role": config.get_str("SHELL_SENDER_ROLE", ""),
        "company": config.get_str("SHELL_SENDER_COMPANY", ""),
        "phone": config.get_str("SHELL_SENDER_PHONE", ""),
        "website": config.get_str("SHELL_SENDER_WEBSITE", ""),
    }


def _build_signature(profile: Dict[str, str], fallback_email: str) -> str:
    name = profile.get("name") or "Shell User"
    role = profile.get("role")
    company = profile.get("company")
    phone = profile.get("phone")
    website = profile.get("website")

    lines = [name]
    if role and company:
        lines.append(f"{role} | {company}")
    elif role:
        lines.append(role)
    elif company:
        lines.append(company)

    if phone:
        lines.append(f"Phone: {phone}")
    if website:
        lines.append(f"Website: {website}")

    lines.append(fallback_email)
    return "\n".join(lines)


def _generate_subject(company_name: str, purpose: str, custom_subject: str = "") -> str:
    if custom_subject and custom_subject.strip():
        return custom_subject.strip()

    purpose_lower = (purpose or "").lower()
    if any(token in purpose_lower for token in ("partnership", "collab", "collaboration", "tie-up")):
        return f"Partnership Proposal for {company_name}"
    if any(token in purpose_lower for token in ("job", "hiring", "career", "position", "resume", "cv")):
        return f"Application Interest - Opportunities at {company_name}"
    if any(token in purpose_lower for token in ("service", "quotation", "quote", "pricing", "proposal")):
        return f"Business Inquiry for {company_name}"
    if any(token in purpose_lower for token in ("support", "help", "issue", "problem")):
        return f"Support Request"

    return f"Professional Inquiry for {company_name}"


def _generate_professional_body(
    company_name: str,
    purpose: str,
    additional_context: str = "",
    tone: str = "formal",
) -> str:
    tone_clean = (tone or "formal").strip().lower()
    if tone_clean not in {"formal", "friendly", "direct"}:
        tone_clean = "formal"

    profile = _sender_profile()
    sender_name = profile.get("name") or "Shell User"

    intro = {
        "formal": f"Dear {company_name} Team,",
        "friendly": f"Hello {company_name} Team,",
        "direct": f"Hi {company_name} Team,",
    }[tone_clean]

    opening = {
        "formal": "I hope you are doing well.",
        "friendly": "I hope your week is going great.",
        "direct": "I am reaching out with a quick request.",
    }[tone_clean]

    core_purpose = _sanitize_text(purpose)
    if not core_purpose:
        core_purpose = "I would like to discuss a potential business opportunity with your team."

    body_lines = [
        intro,
        "",
        opening,
        f"I am writing to connect regarding: {core_purpose}.",
    ]

    context_clean = _sanitize_text(additional_context)
    if context_clean:
        body_lines.append(f"Additional context: {context_clean}.")

    if tone_clean == "formal":
        body_lines.extend(
            [
                "",
                "Please let me know the right point of contact or next steps.",
                "I would appreciate the opportunity to continue this conversation.",
            ]
        )
    elif tone_clean == "friendly":
        body_lines.extend(
            [
                "",
                "If this sounds relevant, I would be happy to continue over email or a short call.",
                "Looking forward to hearing from you.",
            ]
        )
    else:
        body_lines.extend(
            [
                "",
                "Please share the best next step and I will follow up immediately.",
            ]
        )

    body_lines.extend(
        [
            "",
            "Best regards,",
            _build_signature(profile, config.get_str("SHELL_SENDER_EMAIL", "")),
        ]
    )

    return "\n".join(body_lines).strip()


def _validate_attachment_paths(attachments: str) -> Tuple[bool, str, List[str]]:
    """Validate requested attachments before SMTP send."""
    if not attachments:
        return True, "", []

    import os

    home = os.path.realpath(os.path.expanduser("~"))
    cwd = os.path.realpath(os.getcwd())
    allowed_roots = (home, cwd)
    valid_paths: List[str] = []
    for raw_path in attachments.split(","):
        filepath = raw_path.strip()
        if not filepath:
            continue
        if ".." in filepath.replace("\\", "/").split("/"):
            return False, f"attachment path is unsafe: {filepath}", []
        if not os.path.exists(filepath):
            return False, f"attachment file does not exist: {filepath}", []
        real = os.path.realpath(filepath)
        if not any(real == root or real.startswith(root + os.sep) for root in allowed_roots):
            return False, f"attachment outside allowed folders: {filepath}", []
        if not os.path.isfile(real):
            return False, f"attachment is not a file: {filepath}", []
        valid_paths.append(real)

    if attachments.strip() and not valid_paths:
        return False, "no valid attachment files were provided", []
    return True, "", valid_paths


def _build_email_message(
    sender_email: str,
    recipient: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    attachments: str = "",
    html_body: str = "",
) -> EmailMessage:
    msg = EmailMessage()

    if html_body:
        msg.set_content(body)  # plain text fallback
        msg.add_alternative(html_body, subtype='html')
    else:
        msg.set_content(body)

    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = recipient

    cc_clean = ", ".join([a.strip() for a in cc.split(",") if a.strip()])
    if cc_clean:
        msg["Cc"] = cc_clean

    if bcc:
        bcc_clean = ", ".join([a.strip() for a in bcc.split(",") if a.strip()])
        if bcc_clean:
            msg["Bcc"] = bcc_clean

    # Attachments (comma-separated file paths).
    # Security: reject parent-directory traversal and absolute paths
    # escaping a per-user safe root. Users can attach files from their
    # home dir, CWD, or a configured allowlist directory — nothing else.
    if attachments:
        import mimetypes
        import os
        _ok, _reason, valid_paths = _validate_attachment_paths(attachments)
        if not _ok:
            raise ValueError(_reason)
        for filepath in valid_paths:
            mime_type, _ = mimetypes.guess_type(filepath)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            maintype, subtype = mime_type.split('/', 1)
            with open(filepath, 'rb') as f:
                msg.add_attachment(
                    f.read(),
                    maintype=maintype,
                    subtype=subtype,
                    filename=os.path.basename(filepath)
                )

    return msg


def _smtp_send_message(msg: EmailMessage) -> None:
    config = _smtp_config()
    ok, reason = _validate_smtp_credentials(config)
    if not ok:
        raise ValueError(reason)

    server = config["server"]
    port = int(config["port"])
    sender_email = config["sender_email"]
    sender_password = config["sender_password"]
    use_ssl = config["use_ssl"] in {"1", "true", "yes"}

    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, port, context=context, timeout=20) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(server, port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)


def _send_via_web_fallback(
    recipient: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
    auto_send: bool = True,
) -> Tuple[bool, str]:
    try:
        from shell_email_web import gmail_web_mailer
    except Exception as exc:
        return False, f"Gmail web fallback import failed: {exc}"

    try:
        ok, message = gmail_web_mailer.send_mail(
            recipient=recipient,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            auto_send=auto_send,
            headless=False,
        )
        return ok, message
    except Exception as exc:
        return False, f"Gmail web fallback failed: {exc}"


def _google_custom_search(query: str, num: int = 5) -> List[Dict[str, str]]:
    api_key = config.get_str("GOOGLE_SEARCH_API_KEY", "").strip()
    search_engine_id = config.get_str("SEARCH_ENGINE_ID", "").strip()

    if not api_key or not search_engine_id:
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": search_engine_id,
        "q": query,
        "num": max(1, min(10, num)),
    }

    try:
        response = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=10)
        if response.status_code != 200:
            logger.warning("Google CSE failed status=%s for query=%s", response.status_code, query)
            return []
        data = response.json()
        return data.get("items", []) or []
    except Exception as exc:
        logger.warning("Google CSE error for query=%s: %s", query, exc)
        return []


def _extract_emails_from_text(text: str) -> List[str]:
    if not text:
        return []

    cleaned = (
        text.replace("[at]", "@").replace("(at)", "@").replace(" at ", "@")
        .replace("[dot]", ".").replace("(dot)", ".").replace(" dot ", ".")
    )
    emails = [_clean_email(match) for match in EMAIL_REGEX.findall(cleaned)]
    unique: List[str] = []
    seen = set()
    for email in emails:
        if email in seen:
            continue
        if _is_probably_valid_email(email):
            unique.append(email)
            seen.add(email)
    return unique


def _fetch_page_emails(url: str) -> List[str]:
    try:
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=10)
        if resp.status_code != 200:
            return []
        content = resp.text[:250000]
        return _extract_emails_from_text(content)
    except Exception:
        return []


def _score_email_candidate(email: str, target_domain: str, source_url: str) -> int:
    score = 0
    domain = email.split("@", 1)[1]
    local = email.split("@", 1)[0]

    if target_domain and domain == target_domain:
        score += 120
    elif target_domain and domain.endswith("." + target_domain):
        score += 100
    elif target_domain:
        # Hard penalty for unrelated domains to avoid misdirected outreach.
        score -= 90

    if local in PREFERRED_LOCAL_PARTS:
        score += 40

    if any(part in source_url.lower() for part in ("contact", "about", "support", "team")):
        score += 15

    if any(bad in local for bad in BLOCKED_LOCAL_PARTS):
        score -= 200

    if any(bad in local for bad in ("abuse", "spam", "privacy", "legal")):
        score -= 30

    return score


def _domain_matches_target(email_domain: str, target_domain: str) -> bool:
    if not target_domain:
        return True
    return email_domain == target_domain or email_domain.endswith("." + target_domain)


def _discover_company_domain(company_name: str, company_website: str = "") -> str:
    if company_website:
        domain = _extract_domain_from_url(company_website)
        if domain:
            return domain

    search_results = _google_custom_search(f"{company_name} official website", num=3)
    for item in search_results:
        domain = _extract_domain_from_url(item.get("link", ""))
        if domain:
            return domain
    return ""


def _discover_company_email(company_name: str, company_website: str = "") -> Tuple[Optional[str], Dict[str, str]]:
    domain = _discover_company_domain(company_name, company_website)

    queries = [f"{company_name} contact email"]
    if domain:
        queries.extend(
            [
                f"site:{domain} contact",
                f"site:{domain} support email",
                f"site:{domain} \"@{domain}\"",
            ]
        )

    candidates: List[Tuple[str, str, int]] = []
    seen = set()

    for query in queries:
        results = _google_custom_search(query, num=5)
        for item in results:
            snippet = item.get("snippet", "")
            link = item.get("link", "")

            for email in _extract_emails_from_text(snippet):
                key = (email, link)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((email, link, _score_email_candidate(email, domain, link)))

            for email in _fetch_page_emails(link):
                key = (email, link)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((email, link, _score_email_candidate(email, domain, link)))

    if not candidates:
        return None, {"domain": domain, "source": "", "reason": "No public email found"}

    candidates.sort(key=lambda x: x[2], reverse=True)
    selected_pool = candidates
    if domain:
        aligned_candidates = [
            item for item in candidates if _domain_matches_target(item[0].split("@", 1)[1], domain)
        ]
        if aligned_candidates:
            selected_pool = aligned_candidates
        else:
            return None, {
                "domain": domain,
                "source": "",
                "reason": "No domain-aligned email found; manual recipient required for safety",
            }

    best_email, best_source, best_score = selected_pool[0]

    return best_email, {
        "domain": domain,
        "source": best_source,
        "score": str(best_score),
        "reason": "Found from public web sources",
    }


@function_tool(rate_limit="email_send")
def send_email_tool(recipient: str, subject: str, body: str, cc: str = "", bcc: str = "",
                    attachments: str = "", html_body: str = "") -> str:
    """
    Sends an email using SMTP credentials from .env.
    Supports attachments and HTML body.
    Args:
        recipient: Email address to send to.
        subject: Email subject line.
        body: Plain text email body.
        cc: Comma-separated CC addresses (optional).
        bcc: Comma-separated BCC addresses (optional).
        attachments: Comma-separated file paths to attach (optional, e.g., 'C:/Users/report.pdf,C:/Users/data.xlsx').
        html_body: HTML formatted email body (optional). If provided, plain body is used as fallback.
    """
    recipient_clean = _clean_email(recipient)
    if not _is_probably_valid_email(recipient_clean):
        return f"Failed: invalid recipient email '{recipient}'."

    smtp_cfg = _smtp_config()
    ok, reason = _validate_smtp_credentials(smtp_cfg)
    if not ok:
        return f"Failed: {reason}"

    ok, reason, valid_attachments = _validate_attachment_paths(attachments)
    if not ok:
        return f"Failed: {reason}"
    attachments = ",".join(valid_attachments)

    try:
        msg = _build_email_message(
            sender_email=smtp_cfg["sender_email"],
            recipient=recipient_clean,
            subject=subject.strip() or "No Subject",
            body=body.strip() or "",
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            html_body=html_body,
        )
        _smtp_send_message(msg)
        attachment_note = ""
        if attachments:
            import os
            att_names = [os.path.basename(a.strip()) for a in attachments.split(",") if a.strip()]
            attachment_note = f" (Attachments: {', '.join(att_names)})"
        return f"Success: email sent to {recipient_clean}.{attachment_note}"
    except Exception as exc:
        smtp_error = _friendly_smtp_error(exc)
        if _web_fallback_enabled():
            ok_web, web_msg = _send_via_web_fallback(
                recipient=recipient_clean,
                subject=subject.strip() or "No Subject",
                body=body.strip() or "",
                cc=cc,
                bcc=bcc,
                auto_send=True,
            )
            if ok_web:
                return f"Success: SMTP failed, but sent via Gmail Web fallback. ({web_msg})"
            return (
                f"Failed to send email. SMTP error: {smtp_error}. "
                f"Web fallback error: {_friendly_web_fallback_error(web_msg)}"
            )

        return f"Failed to send email: {smtp_error}"


@function_tool
def email_setup_status_tool() -> str:
    """
    Reports whether Shell can send real email right now.
    Does not send anything.
    """
    smtp_cfg = _smtp_config()
    ok, reason = _validate_smtp_credentials(smtp_cfg)
    if ok:
        return (
            "Email credentials are present. Shell can attempt real email through SMTP "
            f"as {smtp_cfg.get('sender_email')}. "
            "This does not guarantee provider login: Gmail will reject normal passwords; "
            "use a Google App Password for SHELL_SENDER_PASSWORD. "
            "For PDFs/files, Shell needs a real existing attachment path; it must not "
            "claim delivery until send_email_tool returns Success."
        )
    return (
        "Email sending is not configured, so Shell must not claim that an email was sent. "
        f"{reason}"
    )


@function_tool
def email_smtp_login_test_tool() -> str:
    """
    Tests SMTP login without sending an email.
    """
    smtp_cfg = _smtp_config()
    ok, reason = _validate_smtp_credentials(smtp_cfg)
    if not ok:
        return f"Failed: {reason}"
    try:
        msg = EmailMessage()
        msg["From"] = smtp_cfg["sender_email"]
        msg["To"] = smtp_cfg["sender_email"]
        msg["Subject"] = "Shell SMTP login test"
        msg.set_content("login test")
        server = smtp_cfg["server"]
        port = int(smtp_cfg["port"])
        use_ssl = smtp_cfg["use_ssl"] in {"1", "true", "yes"}
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(server, port, context=context, timeout=20) as smtp:
                smtp.login(smtp_cfg["sender_email"], smtp_cfg["sender_password"])
        else:
            with smtplib.SMTP(server, port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(smtp_cfg["sender_email"], smtp_cfg["sender_password"])
        return f"Success: SMTP login works for {smtp_cfg['sender_email']}. No email was sent."
    except Exception as exc:
        return f"Failed: {_friendly_smtp_error(exc)}"


@function_tool
def find_company_email_tool(company_name: str, company_website: str = "") -> str:
    """
    Finds a likely public contact email for a company using web search.

    Requires GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID in .env.
    """
    company = _sanitize_text(company_name)
    if not company:
        return "Failed: company_name is required."

    if not config.get_str("GOOGLE_SEARCH_API_KEY", "") or not config.get_str("SEARCH_ENGINE_ID", ""):
        return (
            "Failed: Google Search keys missing. Set GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID in .env "
            "for automatic company email discovery."
        )

    email, meta = _discover_company_email(company, company_website)
    if not email:
        return (
            f"No public email found for '{company}'. "
            f"Domain guess: {meta.get('domain') or 'unknown'}."
        )

    payload = {
        "company": company,
        "email": email,
        "domain": meta.get("domain", ""),
        "source": meta.get("source", ""),
        "confidence_score": meta.get("score", ""),
    }
    return json.dumps(payload, ensure_ascii=True)


@function_tool
def draft_professional_email_tool(
    company_name: str,
    purpose: str,
    additional_context: str = "",
    tone: str = "formal",
    custom_subject: str = "",
) -> str:
    """
    Builds a professional subject/body for outreach.
    """
    company = _sanitize_text(company_name) or "Company"
    subject = _generate_subject(company, purpose, custom_subject=custom_subject)
    body = _generate_professional_body(company, purpose, additional_context=additional_context, tone=tone)

    return json.dumps({"subject": subject, "body": body}, ensure_ascii=True)


@function_tool
def smart_company_email_tool(
    company_name: str,
    purpose: str,
    recipient_email: str = "",
    company_website: str = "",
    additional_context: str = "",
    tone: str = "formal",
    custom_subject: str = "",
    cc: str = "",
    bcc: str = "",
) -> str:
    """
    End-to-end smart email sender.

    Flow:
    1. If recipient_email not provided, discover public company email from internet.
    2. Draft professional subject/body.
    3. Send email from configured sender SMTP.
    """
    company = _sanitize_text(company_name)
    if not company:
        return "Failed: company_name is required."

    if not _sanitize_text(purpose):
        return "Failed: purpose is required so I can draft a professional email."

    config = _smtp_config()
    ok, reason = _validate_smtp_credentials(config)
    if not ok:
        return f"Failed: {reason}"

    recipient = _clean_email(recipient_email)
    discovery_meta: Dict[str, str] = {}

    if recipient and not _is_probably_valid_email(recipient):
        return f"Failed: invalid recipient_email '{recipient_email}'."

    if not recipient:
        if not config.get_str("GOOGLE_SEARCH_API_KEY", "") or not config.get_str("SEARCH_ENGINE_ID", ""):
            return (
                "Failed: recipient_email missing and auto-discovery is not configured. "
                "Set GOOGLE_SEARCH_API_KEY and SEARCH_ENGINE_ID in .env or provide recipient_email directly."
            )

        discovered, meta = _discover_company_email(company, company_website)
        discovery_meta = meta
        if not discovered:
            return (
                f"Failed: could not find a public contact email for {company}. "
                "Please provide recipient_email manually."
            )
        recipient = discovered

    subject = _generate_subject(company, purpose, custom_subject=custom_subject)
    body = _generate_professional_body(company, purpose, additional_context=additional_context, tone=tone)

    try:
        msg = _build_email_message(
            sender_email=config["sender_email"],
            recipient=recipient,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
        )
        _smtp_send_message(msg)

        result = {
            "status": "sent",
            "company": company,
            "recipient": recipient,
            "subject": subject,
            "discovery": discovery_meta,
        }
        return json.dumps(result, ensure_ascii=True)
    except Exception as exc:
        if _web_fallback_enabled():
            ok_web, web_msg = _send_via_web_fallback(
                recipient=recipient,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                auto_send=True,
            )
            if ok_web:
                result = {
                    "status": "sent_via_web_fallback",
                    "company": company,
                    "recipient": recipient,
                    "subject": subject,
                    "discovery": discovery_meta,
                }
                return json.dumps(result, ensure_ascii=True)
            return f"Failed to send smart company email. SMTP error: {exc}. Web fallback error: {web_msg}"

        return f"Failed to send smart company email: {exc}"
