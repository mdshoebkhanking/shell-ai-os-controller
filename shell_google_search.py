from shell_safe_executor import god_tier_tool as function_tool  # ✅ Correct decorator
from datetime import datetime
from shell_config import config
from shell_logger import get_logger
from shell_http import get_async_session
from shell_cache import search_cache

logger = get_logger("google_search")

@function_tool(rate_limit="google_search")
async def google_search(query: str) -> str:
    """
    Searches Google for information using Custom Search API.
    Falls back to DuckDuckGo if Google API keys are missing.
    Args:
        query: Search query string (e.g., 'Python tutorial', 'latest news India').
    """
    logger.info(f"Query: {query}")

    # Check cache first
    cache_key = query.lower().strip()
    if search_cache.has(cache_key):
        logger.info("Cache hit")
        return search_cache.get(cache_key)

    api_key = config.get_str("GOOGLE_SEARCH_API_KEY")
    search_engine_id = config.get_str("SEARCH_ENGINE_ID")

    # Try Google Custom Search first
    if api_key and search_engine_id:
        result = await _google_custom_search(query, api_key, search_engine_id)
        if result and "error" not in result.lower()[:20]:
            search_cache.set(cache_key, result, ttl=300)
            return result
        logger.warning("Google Custom Search failed, trying DuckDuckGo fallback")

    # Fallback: DuckDuckGo (free, no API key needed)
    result = await _duckduckgo_search(query)
    if result:
        search_cache.set(cache_key, result, ttl=300)
        return result

    return "Search results nahi mil rahe. Internet connection check karo."


async def _google_custom_search(query: str, api_key: str, cx: str) -> str:
    """Google Custom Search API."""
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": 8
    }

    try:
        import aiohttp
        session = await get_async_session()
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                body = await response.text()
                logger.error(f"Google API error {response.status}: {body[:300]}")
                if response.status == 403:
                    return "Error: Google Search API 403 — key/cx verify karo"
                return f"Error: Google API {response.status}"

            data = await response.json()
            results = data.get("items", [])

            if not results:
                return ""

            formatted = f"🔍 Google Results for '{query}':\n\n"
            for i, item in enumerate(results, start=1):
                title = item.get("title", "No title")
                link = item.get("link", "")
                snippet = item.get("snippet", "").replace("\n", " ")
                formatted += f"{i}. {title}\n   {link}\n   {snippet}\n\n"

            return formatted.strip()
    except Exception as e:
        logger.error(f"Google search error: {e}")
        return f"Error: {e}"


async def _duckduckgo_search(query: str) -> str:
    """DuckDuckGo Instant Answer API (free, no key needed)."""
    try:
        import aiohttp
        import urllib.parse
        session = await get_async_session()

        # DuckDuckGo HTML search (lite version)
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query}

        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return ""

            html = await response.text()

            # Parse results from HTML
            results = []
            import re
            # Find result blocks
            blocks = re.findall(
                r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )

            if not blocks:
                # Try simpler pattern
                titles = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', html)
                snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                for i, (link, title) in enumerate(titles[:8]):
                    clean_title = re.sub(r'<[^>]+>', '', title).strip()
                    clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                    # Decode DuckDuckGo redirect URL
                    if "uddg=" in link:
                        actual_url = urllib.parse.unquote(re.search(r'uddg=([^&]+)', link).group(1)) if re.search(r'uddg=([^&]+)', link) else link
                    else:
                        actual_url = link
                    results.append((clean_title, actual_url, clean_snippet))
            else:
                for link, title, snippet in blocks[:8]:
                    clean_title = re.sub(r'<[^>]+>', '', title).strip()
                    clean_snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                    if "uddg=" in link:
                        actual_url = urllib.parse.unquote(re.search(r'uddg=([^&]+)', link).group(1)) if re.search(r'uddg=([^&]+)', link) else link
                    else:
                        actual_url = link
                    results.append((clean_title, actual_url, clean_snippet))

            if not results:
                return ""

            formatted = f"🦆 DuckDuckGo Results for '{query}':\n\n"
            for i, (title, link, snippet) in enumerate(results, 1):
                formatted += f"{i}. {title}\n   {link}\n   {snippet}\n\n"

            return formatted.strip()

    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return ""


@function_tool
async def quick_web_answer(question: str) -> str:
    """
    Gets a quick instant answer for factual questions using DuckDuckGo API.
    Args:
        question: A factual question (e.g., 'capital of France', 'who is Elon Musk').
    """
    try:
        import aiohttp
        session = await get_async_session()

        url = "https://api.duckduckgo.com/"
        params = {
            "q": question,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1
        }

        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as response:
            if response.status != 200:
                return await google_search(question)

            data = await response.json(content_type=None)

            # Check for instant answer
            abstract = data.get("AbstractText", "")
            answer = data.get("Answer", "")
            definition = data.get("Definition", "")

            if answer:
                return f"💡 {answer}"
            if abstract:
                source = data.get("AbstractSource", "")
                return f"💡 {abstract}\n\n📚 Source: {source}"
            if definition:
                return f"📖 {definition}"

            # No instant answer, fallback to search
            return await google_search(question)

    except Exception as e:
        logger.error(f"Quick answer error: {e}")
        return await google_search(question)


@function_tool
async def get_current_datetime() -> str:
    """Gets current date, time, day of week."""
    now = datetime.now()
    return (
        f"📅 Date: {now.strftime('%A, %B %d, %Y')}\n"
        f"🕐 Time: {now.strftime('%I:%M:%S %p')}\n"
        f"📆 Week: {now.strftime('%W')} | Day: {now.strftime('%j')}/365"
    )
