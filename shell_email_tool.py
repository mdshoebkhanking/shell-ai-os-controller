import re
import ssl
import json
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





def _is_gmail_api_configured() -> bool:
    import os
    creds_path = config.get_str("SHELL_GMAIL_CREDENTIALS_JSON", "credentials.json").strip()
    token_path = config.get_str("SHELL_GMAIL_TOKEN_JSON", "token.json").strip()
    return os.path.exists(token_path) or os.path.exists(creds_path)


def _get_gmail_service():
    import os
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise ImportError(
            "Gmail API client libraries are missing. Please install them by running:\n"
            "pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        )

    scopes = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.modify'
    ]

    token_path = config.get_str("SHELL_GMAIL_TOKEN_JSON", "token.json").strip()
    creds_path = config.get_str("SHELL_GMAIL_CREDENTIALS_JSON", "credentials.json").strip()
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError(
                    f"Gmail API credentials file not found at '{creds_path}'. "
                    "Please download OAuth Client ID credentials (JSON format) from the Google Cloud Console "
                    "and place the file in the workspace directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0, timeout=120)
        
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return build('gmail', 'v1', credentials=creds)


def _send_email_via_gmail_api(sender_email: str, recipient: str, subject: str, body: str, 
                              cc: str = "", bcc: str = "", attachments: str = "", html_body: str = "") -> bool:
    import base64
    import os
    import mimetypes
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    service = _get_gmail_service()

    if attachments or html_body:
        msg = MIMEMultipart()
        msg['to'] = recipient
        msg['subject'] = subject
        if cc:
            msg['cc'] = cc
        if bcc:
            msg['bcc'] = bcc
            
        if html_body:
            msg_alternative = MIMEMultipart('alternative')
            msg.attach(msg_alternative)
            msg_alternative.attach(MIMEText(body, 'plain'))
            msg_alternative.attach(MIMEText(html_body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
            
        if attachments:
            for path in attachments.split(','):
                path = path.strip()
                if not path or not os.path.exists(path):
                    continue
                filename = os.path.basename(path)
                content_type, encoding = mimetypes.guess_type(path)
                if content_type is None or encoding is not None:
                    content_type = 'application/octet-stream'
                main_type, sub_type = content_type.split('/', 1)
                with open(path, 'rb') as fp:
                    part = MIMEBase(main_type, sub_type)
                    part.set_payload(fp.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', 'attachment', filename=filename)
                msg.attach(part)
    else:
        msg = MIMEText(body)
        msg['to'] = recipient
        msg['subject'] = subject
        if cc:
            msg['cc'] = cc
        if bcc:
            msg['bcc'] = bcc

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
    send_body = {'raw': raw_message}
    service.users().messages().send(userId='me', body=send_body).execute()
    return True





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
    """Validate requested attachments before Gmail API send."""
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
    Sends an email using Gmail API.
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
        return json.dumps({"success": False, "error": f"Failed: invalid recipient email '{recipient}'."}, ensure_ascii=True)

    ok, reason, valid_attachments = _validate_attachment_paths(attachments)
    if not ok:
        return json.dumps({"success": False, "error": f"Failed: {reason}"}, ensure_ascii=True)
    attachments = ",".join(valid_attachments)

    if not _is_gmail_api_configured():
        return json.dumps({
            "success": False,
            "error": "Failed: Gmail API is not configured. Please place your client credentials.json in the workspace root."
        }, ensure_ascii=True)

    try:
        _send_email_via_gmail_api(
            sender_email="",
            recipient=recipient_clean,
            subject=subject.strip() or "No Subject",
            body=body.strip() or "",
            cc=cc,
            bcc=bcc,
            attachments=attachments,
            html_body=html_body,
        )
        return json.dumps({"success": True, "error": None}, ensure_ascii=True)
    except Exception as exc:
        logger.error("Gmail API send failed: %s", exc)
        return json.dumps({"success": False, "error": f"Failed to send email via Gmail API: {exc}"}, ensure_ascii=True)


@function_tool
def email_setup_status_tool() -> str:
    """
    Reports whether Shell can send real email right now.
    Does not send anything.
    """
    import os
    # Check Gmail API status first
    gmail_api_available = False
    try:
        from googleapiclient.discovery import build
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.oauth2.credentials import Credentials
        gmail_api_available = True
    except ImportError:
        pass

    creds_path = config.get_str("SHELL_GMAIL_CREDENTIALS_JSON", "credentials.json").strip()
    token_path = config.get_str("SHELL_GMAIL_TOKEN_JSON", "token.json").strip()

    if _is_gmail_api_configured():
        if not gmail_api_available:
            return (
                "Gmail API credentials are detected, but the required client libraries are missing. "
                "Please run: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
            )
        if os.path.exists(token_path):
            return "Gmail API setup status: ready and authorized (token.json present). Shell can read, search, draft, and send emails using the Gmail API."
        else:
            return f"Gmail API setup status: credentials file present ({creds_path}) but not authorized. The next email command will trigger a browser authorization flow."

    return "Email sending is not configured. Please place your client credentials.json in the workspace root to enable Gmail API."


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
    3. Send email from Gmail API.
    """
    company = _sanitize_text(company_name)
    if not company:
        return "Failed: company_name is required."

    if not _sanitize_text(purpose):
        return "Failed: purpose is required so I can draft a professional email."

    if not _is_gmail_api_configured():
        return "Failed: Gmail API is not configured. Please place your client credentials.json in the workspace root."

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
        if not _is_gmail_api_configured():
            return "Failed to send smart company email: Gmail API is not configured."
        _send_email_via_gmail_api(
            sender_email="",
            recipient=recipient,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
        )

        result = {
            "status": "sent",
            "company": company,
            "recipient": recipient,
            "subject": subject,
            "discovery": discovery_meta,
        }
        return json.dumps(result, ensure_ascii=True)
    except Exception as exc:
        return f"Failed to send smart company email: {exc}"


@function_tool
def research_and_email_tool(topic: str, recipient: str) -> str:
    """
    Does deep AI research on a topic and emails a detailed HTML report.
    Args:
        topic: The topic or subject to research.
        recipient: Email address to send the report to.
    """
    import time

    recipient_clean = _clean_email(recipient)
    if not _is_probably_valid_email(recipient_clean):
        return json.dumps({"success": False, "error": f"Invalid recipient: '{recipient}'"}, ensure_ascii=True)



    if not _is_gmail_api_configured():
        return json.dumps({"success": False, "error": "Email not configured: Gmail API is missing credentials.json"}, ensure_ascii=True)

    topic_clean = str(topic or "").strip()
    if not topic_clean:
        return json.dumps({"success": False, "error": "Topic is required."}, ensure_ascii=True)

    # --- Step 1: Research using AI brain ---
    research_text = ""
    try:
        from brain.core import MultiAIBrain
        brain = MultiAIBrain.get_instance()
        research_prompt = (
            f"Do a comprehensive, detailed deep research report on: {topic_clean}.\n\n"
            "Include:\n"
            "- Overview / Introduction\n"
            "- Key facts and specifications (if applicable)\n"
            "- History and background\n"
            "- Current status / latest developments (2024-2025)\n"
            "- Pros and cons (if applicable)\n"
            "- Expert opinions and community feedback\n"
            "- Conclusion and recommendations\n\n"
            "Write in clear, informative paragraphs. Be thorough and detailed."
        )
        research_text = str(
            brain.generate_response_sync(research_prompt, mode="STANDARD") or ""
        ).strip()
    except Exception as exc:
        logger.warning("Brain research failed for topic=%s: %s", topic_clean, exc)

    # Fallback: web search snippets
    if not research_text or len(research_text) < 100:
        try:
            results = _google_custom_search(f"{topic_clean} comprehensive overview", num=5)
            if results:
                snippets = []
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    link = item.get("link", "")
                    if snippet:
                        snippets.append(f"<b>{title}</b>: {snippet} <i>({link})</i>")
                research_text = f"Research findings for '{topic_clean}':\n\n" + "\n\n".join(snippets)
        except Exception as exc:
            logger.warning("Web search fallback failed: %s", exc)

    if not research_text:
        research_text = (
            f"Deep research on '{topic_clean}' was attempted but could not retrieve "
            "detailed information. Please enable internet research for richer results."
        )

    # --- Step 2: Build HTML email ---
    timestamp = time.strftime("%d %B %Y, %I:%M %p")
    paragraphs = [p.strip() for p in research_text.split("\n\n") if p.strip()]
    html_paragraphs = ""
    for para in paragraphs:
        lines = para.split("\n")
        if para.startswith(("*", "-", "\u2022")):
            items = [li.lstrip("*-\u2022 ").strip() for li in lines if li.strip()]
            items_html = "".join(f"<li style='margin-bottom:6px;'>{item}</li>" for item in items)
            html_paragraphs += f"<ul style='margin:8px 0 16px 20px;color:#d1d5db;'>{items_html}</ul>"
        elif para.startswith("#"):
            heading = para.lstrip("#").strip()
            html_paragraphs += f"<h3 style='color:#818cf8;margin:20px 0 8px;font-size:16px;border-bottom:1px solid rgba(129,140,248,0.2);padding-bottom:6px;'>{heading}</h3>"
        else:
            html_paragraphs += f"<p style='margin:0 0 14px;color:#d1d5db;line-height:1.75;'>{para}</p>"

    html_body = f"""<!DOCTYPE html>
<html lang='en'>
<head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Shell AI Research Report</title></head>
<body style='margin:0;padding:0;background:#0a0a14;font-family:Inter,Segoe UI,Arial,sans-serif;'>
  <div style='max-width:700px;margin:32px auto;background:linear-gradient(160deg,#1a1a2e 0%,#12122a 100%);border-radius:20px;overflow:hidden;border:1px solid rgba(99,102,241,0.25);box-shadow:0 24px 80px rgba(0,0,0,0.6);'>
    <div style='background:linear-gradient(135deg,#4338ca,#7c3aed);padding:36px;'>
      <p style='color:rgba(255,255,255,0.6);font-size:12px;text-transform:uppercase;letter-spacing:1.5px;margin:0 0 8px;'>Shell AI &bull; Deep Research Report</p>
      <h1 style='color:#fff;font-size:26px;font-weight:700;margin:0 0 6px;letter-spacing:-0.5px;'>\U0001f52c {topic_clean}</h1>
      <p style='color:rgba(255,255,255,0.7);font-size:13px;margin:0;'>{timestamp}</p>
    </div>
    <div style='padding:32px 36px;'>
      <div style='background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:28px;'>
        {html_paragraphs}
      </div>
    </div>
    <div style='background:rgba(0,0,0,0.35);padding:18px 36px;border-top:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:8px;'>
      <span style='font-size:16px;'>\U0001f916</span>
      <p style='color:#6b7280;font-size:12px;margin:0;'>Generated by <strong style='color:#818cf8;'>Shell AI</strong> &bull; Developed by <strong style='color:#a78bfa;'>mdshoebking</strong></p>
    </div>
  </div>
</body></html>"""

    plain_body = f"Shell AI Deep Research Report\nTopic: {topic_clean}\nGenerated: {timestamp}\n\n{research_text}"

    if not _is_gmail_api_configured():
        return json.dumps({"success": False, "error": "Gmail API is not configured."}, ensure_ascii=True)

    try:
        _send_email_via_gmail_api(
            sender_email="",
            recipient=recipient_clean,
            subject=f"\U0001f52c Deep Research: {topic_clean}",
            body=plain_body,
            html_body=html_body,
        )
        return json.dumps({"success": True, "error": None, "topic": topic_clean, "recipient": recipient_clean}, ensure_ascii=True)
    except Exception as exc:
        logger.error("Gmail API send failed: %s", exc)
        return json.dumps({"success": False, "error": f"Failed to send email via Gmail API: {exc}"}, ensure_ascii=True)


@function_tool
def gmail_read_inbox_tool(max_results: int = 5) -> str:
    """
    Reads the latest emails from the Gmail inbox.
    Args:
        max_results: Maximum number of emails to retrieve (default 5).
    """
    import json

    if not _is_gmail_api_configured():
        return json.dumps({
            "success": False,
            "error": "Gmail API is not configured. Please place your client credentials.json in the workspace root.",
            "emails": []
        }, ensure_ascii=True)

    try:
        service = _get_gmail_service()
        results = service.users().messages().list(userId='me', q='in:inbox', maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        emails_list = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            from_ = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown Date')
            
            snippet = msg.get('snippet', '')
            body = ""
            
            def parse_parts(parts):
                text_body = ""
                for part in parts:
                    mime_type = part.get('mimeType', '')
                    body_data = part.get('body', {}).get('data', '')
                    if mime_type == 'text/plain' and body_data:
                        import base64
                        text_body += base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
                        break
                    elif 'parts' in part:
                        sub_body = parse_parts(part['parts'])
                        if sub_body:
                            text_body += sub_body
                            break
                return text_body

            if 'parts' in payload:
                body = parse_parts(payload['parts'])
            else:
                body_data = payload.get('body', {}).get('data', '')
                if body_data:
                    import base64
                    body = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            
            if not body:
                body = snippet
            cleaned_snippet = " ".join(body.split())[:200]
            
            emails_list.append({
                "from": from_,
                "subject": subject,
                "date": date,
                "snippet": cleaned_snippet
            })
            
        return json.dumps({
            "success": True,
            "error": None,
            "emails": emails_list
        }, ensure_ascii=True)
    except Exception as exc:
        logger.error("Gmail API read failed: %s", exc)
        return json.dumps({
            "success": False,
            "error": f"Gmail API read failed: {exc}",
            "emails": []
        }, ensure_ascii=True)


@function_tool
def gmail_create_draft_tool(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> str:
    """
    Creates a draft email in the Gmail Drafts folder.
    Args:
        to: Recipient email address.
        subject: Email subject.
        body: Plain text email body.
        cc: Comma-separated CC email addresses (optional).
        bcc: Comma-separated BCC email addresses (optional).
    """
    import json

    if not _is_gmail_api_configured():
        return json.dumps({
            "success": False,
            "error": "Gmail API is not configured. Please place your client credentials.json in the workspace root."
        }, ensure_ascii=True)

    try:
        service = _get_gmail_service()
        from email.mime.text import MIMEText
        import base64
        
        mime_msg = MIMEText(body)
        mime_msg['to'] = to
        mime_msg['subject'] = subject
        if cc:
            mime_msg['cc'] = cc
        if bcc:
            mime_msg['bcc'] = bcc
            
        raw_message = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode('utf-8')
        draft_body = {
            'message': {
                'raw': raw_message
            }
        }
        
        draft = service.users().drafts().create(userId='me', body=draft_body).execute()
        return json.dumps({"success": True, "error": None}, ensure_ascii=True)
    except Exception as exc:
        logger.error("Gmail API draft creation failed: %s", exc)
        return json.dumps({
            "success": False,
            "error": f"Gmail API draft creation failed: {exc}"
        }, ensure_ascii=True)
