import asyncio
from shell_safe_executor import god_tier_tool as function_tool
from shell_config import config
from shell_logger import get_logger
from shell_http import get_async_session
from shell_cache import api_cache

logger = get_logger("shell_news")

@function_tool(rate_limit="news_api")
async def get_latest_news_tool(topic: str = "technology", language: str = "en") -> str:
    """
    Fetches the latest news headlines using NewsData.io API.
    Args:
        topic: Keyword to search (e.g., 'technology', 'sports', 'india', 'cricket', 'AI').
        language: Language code (e.g., 'en', 'hi').
    """
    NEWS_API_KEY = config.get_str("NEWS_API_KEY")

    if not NEWS_API_KEY or "pub_" not in NEWS_API_KEY:
        return "❌ News API Key missing or invalid. Please check .env file."

    cache_key = f"news:{topic}:{language}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    try:
        import aiohttp
        url = "https://newsdata.io/api/1/news"
        params = {
            "apikey": NEWS_API_KEY,
            "q": topic,
            "language": language
        }

        session = await get_async_session()
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as response:
            if response.status != 200:
                return f"❌ News API Error: {response.status}"

            data = await response.json()
            results = data.get("results", [])

            if not results:
                return f"⚠️ No news found for '{topic}'."

            # Format output with more detail
            news_list = [f"📰 TOP HEADLINES — '{topic.upper()}' ({language.upper()}):\n"]
            for i, item in enumerate(results[:8]):
                title = item.get("title", "No Title")
                link = item.get("link", "#")
                source = item.get("source_id", "Unknown")
                pub_date = item.get("pubDate", "")
                description = item.get("description", "")

                # Trim description
                if description and len(description) > 120:
                    description = description[:117] + "..."

                entry = f"{i+1}. {title}\n"
                if description:
                    entry += f"   {description}\n"
                entry += f"   📌 {source}"
                if pub_date:
                    entry += f" | 🕐 {pub_date[:16]}"
                entry += f"\n   🔗 {link}"

                news_list.append(entry)

            result = "\n\n".join(news_list)
            api_cache.set(cache_key, result, ttl=300)
            return result

    except Exception as e:
        return f"❌ Error fetching news: {e}"


@function_tool(rate_limit="news_api")
async def get_trending_news_tool(country: str = "in", category: str = "") -> str:
    """
    Gets trending/top news headlines by country and category.
    Args:
        country: Country code (e.g., 'in' for India, 'us' for USA, 'gb' for UK).
        category: Optional category — 'business', 'entertainment', 'health', 'science', 'sports', 'technology', 'politics'.
    """
    NEWS_API_KEY = config.get_str("NEWS_API_KEY")
    if not NEWS_API_KEY or "pub_" not in NEWS_API_KEY:
        return "❌ News API Key missing."

    cache_key = f"trending:{country}:{category}"
    cached = api_cache.get(cache_key)
    if cached:
        return cached

    try:
        import aiohttp
        url = "https://newsdata.io/api/1/latest"
        params = {
            "apikey": NEWS_API_KEY,
            "country": country,
        }
        if category:
            params["category"] = category

        session = await get_async_session()
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as response:
            if response.status != 200:
                return f"❌ Trending news error: {response.status}"

            data = await response.json()
            results = data.get("results", [])

            if not results:
                return f"⚠️ No trending news for {country.upper()}."

            cat_label = f" [{category.upper()}]" if category else ""
            news_list = [f"🔥 TRENDING NEWS — {country.upper()}{cat_label}:\n"]

            for i, item in enumerate(results[:8]):
                title = item.get("title", "No Title")
                link = item.get("link", "#")
                source = item.get("source_id", "")
                pub_date = item.get("pubDate", "")

                entry = f"{i+1}. {title}"
                if source:
                    entry += f"\n   📌 {source}"
                if pub_date:
                    entry += f" | 🕐 {pub_date[:16]}"
                entry += f"\n   🔗 {link}"

                news_list.append(entry)

            result = "\n\n".join(news_list)
            api_cache.set(cache_key, result, ttl=300)
            return result

    except Exception as e:
        return f"❌ Error: {e}"


@function_tool
async def get_news_categories() -> str:
    """Lists available news categories for search."""
    return (
        "📰 Available News Categories:\n\n"
        "1. technology — Tech, AI, Gadgets\n"
        "2. sports — Cricket, Football, Tennis\n"
        "3. business — Markets, Economy, Startups\n"
        "4. entertainment — Movies, Music, Celebrities\n"
        "5. health — Medical, Fitness, Wellness\n"
        "6. science — Space, Research, Discoveries\n"
        "7. politics — Government, Elections, Policy\n\n"
        "Countries: in (India), us (USA), gb (UK), au (Australia), ca (Canada)\n\n"
        "Usage: 'trending news India sports' ya 'latest AI news'"
    )
