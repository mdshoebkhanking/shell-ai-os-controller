
import asyncio
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger("shell_web_automation")

class WebGod:
    """
    Web automation engine (v3)
    
    Capabilities:
    - Parallel browsing workers when available.
    - Browser automation with Playwright.
    - Content extraction from web pages.
    - Form assistance through controlled selectors/actions.
    """
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.active_pages: List[Page] = []
        
    async def initialize(self):
        """Starts the Playwright engine."""
        if not self.playwright:
            self.playwright = await async_playwright().start()
            # Launch in Headless mode for speed, but with stealth args
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--window-position=0,0",
                    "--ignore-certifcate-errors",
                    "--ignore-certifcate-errors-spki-list",
                    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ]
            )
            self.context = await self.browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            logger.info("🌐 Web automation engine initialized")

    async def parallel_search(self, query: str, num_sources: int = 5) -> str:
        """
        Executes a search across multiple engines/sites simultaneously.
        """
        if not self.playwright:
            await self.initialize()

        logger.info(f"🚀 Launching Parallel Search for: {query}")
        
        # Define diverse search targets
        targets = [
            f"https://www.google.com/search?q={query}",
            f"https://duckduckgo.com/?q={query}",
            f"https://www.bing.com/search?q={query}",
            # Add niche targets if needed
        ][:num_sources]
        
        tasks = [self._scrape_page(url) for url in targets]
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        summary = self._synthesize_results(results)
        return summary

    async def _scrape_page(self, url: str) -> Dict:
        """Helper to scrape a single page quickly."""
        try:
            # Re-initialize context if closed/missing
            if not self.context:
                await self.initialize()
                
            page = await self.context.new_page()
            self.active_pages.append(page)
            
            logger.info(f"🕸️ Web automation accessing {url}")
            
            # Increased timeout to 30s and more lenient wait condition
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"⚠️ Page Load Timeout/Error ({url}): {e}. Attempting extraction anyway.")

            # Simple extraction heuristic
            try:
                title = await page.title()
            except Exception:
                title = "No Title"

            try:
                # Fallback to simple evaluation if text extraction fails
                content = await page.evaluate("() => document.body.innerText")
            except Exception:
                content = "Content extraction failed."

            
            await page.close()
            if page in self.active_pages:
                self.active_pages.remove(page)
            
            return {
                "source": url,
                "title": title,
                "content": content[:1500] + "...", # Increased buffer
                "status": "success"
            }
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {e}")
            return {"source": url, "error": str(e), "status": "failed"}

    def _synthesize_results(self, results: List[Dict]) -> str:
        """Merges multiple search results into a coherent answer."""
        # In a real implementation, we would pass this to an LLM for summarization.
        # For now, we just concatenate headers.
        
        summary = "🌐 **Global Search Synthesis**\n\n"
        for i, res in enumerate(results):
            if "error" in res:
                continue
            clean_content = res['content'][:200].replace('\n', ' ')
            summary += f"{i+1}. **{res['title']}**\n   {clean_content}\n\n"
            
        return summary

    async def shutdown(self):
        """Clean shutdown of browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("🌐 Web God Engine Shutdown")

# Singleton
web_god = WebGod()
