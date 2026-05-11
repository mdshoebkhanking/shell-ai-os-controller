"""
Shell Translator Tools v1.0
------------------------------
Translation tools for Shell AI.
Translate text, detect languages, translate files, and list supported languages.

Uses deep_translator (GoogleTranslator) with httpx fallback.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool
"""

import os
import json
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_translator")


# Supported language codes (common subset)
LANGUAGE_MAP = {
    "af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic",
    "hy": "Armenian", "az": "Azerbaijani", "eu": "Basque", "be": "Belarusian",
    "bn": "Bengali", "bs": "Bosnian", "bg": "Bulgarian", "ca": "Catalan",
    "zh-CN": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)",
    "hr": "Croatian", "cs": "Czech", "da": "Danish", "nl": "Dutch",
    "en": "English", "et": "Estonian", "fi": "Finnish", "fr": "French",
    "de": "German", "el": "Greek", "gu": "Gujarati", "ha": "Hausa",
    "he": "Hebrew", "hi": "Hindi", "hu": "Hungarian", "is": "Icelandic",
    "id": "Indonesian", "it": "Italian", "ja": "Japanese", "kn": "Kannada",
    "ko": "Korean", "la": "Latin", "lv": "Latvian", "lt": "Lithuanian",
    "mk": "Macedonian", "ms": "Malay", "ml": "Malayalam", "mr": "Marathi",
    "mn": "Mongolian", "ne": "Nepali", "no": "Norwegian", "ps": "Pashto",
    "fa": "Persian", "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi",
    "ro": "Romanian", "ru": "Russian", "sr": "Serbian", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "es": "Spanish", "sw": "Swahili",
    "sv": "Swedish", "ta": "Tamil", "te": "Telugu", "th": "Thai",
    "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek",
    "vi": "Vietnamese", "cy": "Welsh", "yo": "Yoruba", "zu": "Zulu",
    "auto": "Auto-detect",
}


def _get_translator(source: str, target: str):
    """Get a translator instance using best available library."""
    # Try deep_translator first
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=source, target=target), "deep_translator"
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    # Try googletrans
    try:
        from googletrans import Translator
        return Translator(), "googletrans"
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    return None, None


def _translate_with_httpx(text: str, target: str, source: str = "auto") -> str:
    """Fallback translation using httpx/requests with Google Translate web API."""
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source,
        "tl": target,
        "dt": "t",
        "q": text,
    }

    # Try httpx
    try:
        import httpx
        response = httpx.get(url, params=params, timeout=10)
        result = response.json()
        translated = "".join(part[0] for part in result[0] if part[0])
        return translated
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    # Try requests
    try:
        import requests
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        translated = "".join(part[0] for part in result[0] if part[0])
        return translated
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    # Try urllib (stdlib)
    try:
        import urllib.request
        import urllib.parse
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part in data[0] if part[0])
            return translated
    except Exception as e:
        raise RuntimeError(
            f"No HTTP library available for translation fallback. Error: {e}\n"
            "Install deep_translator: pip install deep_translator"
        )


# ================================================================
#  TOOL 1: TRANSLATE TEXT
# ================================================================

_LANG_NAME_TO_CODE = {v.lower(): k for k, v in LANGUAGE_MAP.items() if k != "auto"}
# Add common aliases
_LANG_NAME_TO_CODE.update({
    "chinese": "zh-CN", "mandarin": "zh-CN", "portuguese": "pt",
    "brazilian": "pt", "farsi": "fa", "persian": "fa",
})


def _parse_target_from_text(text: str):
    """Parse 'translate X to/in LANG' → (text_to_translate, lang_code) or (text, None)."""
    import re
    # Match patterns like "... to spanish", "... in french", "... into german"
    m = re.search(r'^(.+?)\s+(?:to|in|into)\s+(\w[\w\s\-]*?)\s*$', text, re.IGNORECASE)
    if m:
        body, lang_str = m.group(1).strip(), m.group(2).strip().lower()
        # Check if lang_str is a language name
        if lang_str in _LANG_NAME_TO_CODE:
            return body, _LANG_NAME_TO_CODE[lang_str]
        # Check if it's already a language code
        if lang_str in LANGUAGE_MAP:
            return body, lang_str
    return text, None


@function_tool
async def translate_text_tool(text: str, target_lang: str = "") -> str:
    """
    Translate text to a target language.
    Args:
        text: The text to translate (can include target like 'hello to spanish').
        target_lang: Target language code or name (e.g., 'es', 'french', 'de'). Optional if included in text.
    """
    if not text or not text.strip():
        return "Error: No text provided to translate."

    # If target_lang not provided, try to parse it from the text
    if not target_lang or not target_lang.strip():
        text, parsed_lang = _parse_target_from_text(text.strip())
        if parsed_lang:
            target_lang = parsed_lang
        else:
            return (
                "Error: No target language specified.\n"
                "Say something like: 'translate hello to spanish'\n"
                "Or use a language code: 'es', 'fr', 'de', 'ja', 'hi'"
            )
    else:
        target_lang = target_lang.strip().lower()
        # Allow language names as well as codes
        if target_lang in _LANG_NAME_TO_CODE:
            target_lang = _LANG_NAME_TO_CODE[target_lang]

    if target_lang not in LANGUAGE_MAP and target_lang != "auto":
        return (
            f"Error: Unknown language '{target_lang}'.\n"
            f"Use supported_languages_tool() to see available codes."
        )

    translator, lib_name = _get_translator(source="auto", target=target_lang)

    try:
        if lib_name == "deep_translator":
            translated = translator.translate(text)
        elif lib_name == "googletrans":
            result = translator.translate(text, dest=target_lang)
            translated = result.text
        else:
            translated = _translate_with_httpx(text, target_lang)

        lang_name = LANGUAGE_MAP.get(target_lang, target_lang)
        return (
            f"Translation to {lang_name} ({target_lang}):\n"
            f"{'=' * 40}\n"
            f"Original : {text[:200]}{'...' if len(text) > 200 else ''}\n"
            f"Translated: {translated}"
        )
    except Exception as e:
        return f"Error translating text: {e}"


# ================================================================
#  TOOL 2: DETECT LANGUAGE
# ================================================================

@function_tool
async def detect_language_tool(text: str) -> str:
    """
    Detect the language of a given text.
    Args:
        text: The text to analyze for language detection.
    """
    if not text or not text.strip():
        return "Error: No text provided for language detection."

    # Try deep_translator
    try:
        from deep_translator import single_detection
        lang_code = single_detection(text, api_key=None)
        lang_name = LANGUAGE_MAP.get(lang_code, lang_code)
        return f"Detected language: {lang_name} ({lang_code})"
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    # Try googletrans
    try:
        from googletrans import Translator
        translator = Translator()
        detected = translator.detect(text)
        lang_code = detected.lang
        confidence = getattr(detected, "confidence", "N/A")
        lang_name = LANGUAGE_MAP.get(lang_code, lang_code)
        return (
            f"Detected language: {lang_name} ({lang_code})\n"
            f"Confidence: {confidence}"
        )
    except ImportError as _e:
        logger.debug("ignored ImportError: %s", _e)
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    # Fallback using Google Translate API
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": text[:200]}

        import urllib.request
        import urllib.parse
        query_string = urllib.parse.urlencode(params)
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            detected_lang = data[2] if len(data) > 2 else "unknown"
            lang_name = LANGUAGE_MAP.get(detected_lang, detected_lang)
            return f"Detected language: {lang_name} ({detected_lang})"
    except Exception as e:
        return f"Error detecting language: {e}"


# ================================================================
#  TOOL 3: TRANSLATE FILE
# ================================================================

@function_tool
async def translate_file_tool(filepath: str, target_lang: str) -> str:
    """
    Read a text file and translate its contents to the target language.
    Args:
        filepath: Path to the text file to translate.
        target_lang: Target language code (e.g., 'es', 'fr', 'de').
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    target_lang = target_lang.strip().lower()
    if target_lang not in LANGUAGE_MAP:
        return f"Error: Unknown language code '{target_lang}'."

    try:
        # Try different encodings
        content = None
        for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
            try:
                with open(filepath, "r", encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue

        if content is None:
            return "Error: Could not read file with any supported encoding."

        if not content.strip():
            return "Error: File is empty."

        if len(content) > 5000:
            return (
                f"Error: File is too large ({len(content)} characters). "
                "Maximum supported size is 5000 characters. "
                "Split the file into smaller parts first."
            )

        translator, lib_name = _get_translator(source="auto", target=target_lang)

        if lib_name == "deep_translator":
            # deep_translator has a 5000 char limit, chunk if needed
            translated = translator.translate(content)
        elif lib_name == "googletrans":
            result = translator.translate(content, dest=target_lang)
            translated = result.text
        else:
            translated = _translate_with_httpx(content, target_lang)

        # Save translated file
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_{target_lang}{ext}"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(translated)

        lang_name = LANGUAGE_MAP.get(target_lang, target_lang)
        return (
            f"Successfully translated file to {lang_name}.\n"
            f"  Source  : {os.path.basename(filepath)} ({len(content)} chars)\n"
            f"  Output  : {output_path}\n"
            f"  Language: {lang_name} ({target_lang})"
        )
    except Exception as e:
        return f"Error translating file: {e}"


# ================================================================
#  TOOL 4: SUPPORTED LANGUAGES
# ================================================================

@function_tool
async def supported_languages_tool() -> str:
    """
    List all supported languages and their codes for translation.
    """
    lines = [
        "Supported Languages for Translation:",
        "=" * 45,
    ]

    # Sort by language name
    sorted_langs = sorted(LANGUAGE_MAP.items(), key=lambda x: x[1])

    for code, name in sorted_langs:
        if code == "auto":
            continue
        lines.append(f"  {code:<8} {name}")

    lines.append(f"\nTotal: {len(LANGUAGE_MAP) - 1} languages")
    lines.append("Tip: Use 'auto' as source language for auto-detection.")

    return "\n".join(lines)
