"""
Shell Stock Tools - Stock & Crypto Price Data
-----------------------------------------------
Provides tools for fetching stock prices, history,
company info, and cryptocurrency prices.
"""

import asyncio
import json
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("SHELL_STOCK")

# ── Soft imports ─────────────────────────────────────
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    import urllib.request
    import urllib.error
    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False


def _fetch_url_json(url: str, timeout: int = 15) -> dict:
    """Fetch JSON from a URL using urllib (stdlib)."""
    req = urllib.request.Request(url, headers={"User-Agent": "ShellAI/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


@function_tool
async def stock_price_tool(symbol: str) -> str:
    """
    Get current stock price for a given ticker symbol.
    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'GOOGL', 'TSLA', 'RELIANCE.NS').
    """
    try:
        if not YFINANCE_AVAILABLE:
            return "Error: yfinance is not installed. Run: pip install yfinance"

        symbol = symbol.upper().strip()

        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return info

        info = await asyncio.to_thread(_fetch)

        if not info or "regularMarketPrice" not in info:
            # Try fast_info as fallback
            def _fetch_fast():
                ticker = yf.Ticker(symbol)
                fast = ticker.fast_info
                return {
                    "price": getattr(fast, "last_price", None),
                    "prev_close": getattr(fast, "previous_close", None),
                    "currency": getattr(fast, "currency", "USD"),
                }
            fast = await asyncio.to_thread(_fetch_fast)
            if fast["price"]:
                change = 0
                if fast["prev_close"] and fast["prev_close"] > 0:
                    change = ((fast["price"] - fast["prev_close"]) / fast["prev_close"]) * 100
                return (
                    f"Stock: {symbol}\n"
                    f"Price: {fast['currency']} {fast['price']:.2f}\n"
                    f"Prev Close: {fast['currency']} {fast['prev_close']:.2f}\n"
                    f"Change: {change:+.2f}%"
                )
            return f"Could not fetch price for symbol: {symbol}"

        price = info.get("regularMarketPrice") or info.get("currentPrice", "N/A")
        prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose", 0)
        currency = info.get("currency", "USD")
        name = info.get("shortName", symbol)
        market_state = info.get("marketState", "unknown")

        change = 0
        if prev_close and price != "N/A" and prev_close > 0:
            change = ((price - prev_close) / prev_close) * 100

        lines = [
            f"Stock: {name} ({symbol})",
            f"Price: {currency} {price}",
            f"Prev Close: {currency} {prev_close}",
            f"Change: {change:+.2f}%",
            f"Market: {market_state}",
        ]

        day_high = info.get("dayHigh")
        day_low = info.get("dayLow")
        if day_high and day_low:
            lines.append(f"Day Range: {currency} {day_low} - {day_high}")

        volume = info.get("volume")
        if volume:
            lines.append(f"Volume: {volume:,}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"stock_price_tool error: {e}")
        return f"Error fetching stock price: {e}"


@function_tool
async def stock_history_tool(symbol: str, period: str = "1mo") -> str:
    """
    Get stock price history for a given period.
    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'TSLA').
        period: Time period - '1d', '5d', '1mo', '3mo', '6mo', '1y', '5y'.
    """
    try:
        if not YFINANCE_AVAILABLE:
            return "Error: yfinance is not installed. Run: pip install yfinance"

        valid_periods = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
        period = period.lower().strip()
        if period not in valid_periods:
            return f"Invalid period: {period}. Valid: {', '.join(valid_periods)}"

        symbol = symbol.upper().strip()

        def _fetch():
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            return hist

        hist = await asyncio.to_thread(_fetch)

        if hist.empty:
            return f"No history data for {symbol} ({period})"

        lines = [f"Price History: {symbol} ({period})", "-" * 50]

        # Show at most 20 rows
        step = max(1, len(hist) // 20)
        for i in range(0, len(hist), step):
            row = hist.iloc[i]
            date_str = str(hist.index[i].date())
            lines.append(
                f"  {date_str}  Open: {row['Open']:.2f}  High: {row['High']:.2f}  "
                f"Low: {row['Low']:.2f}  Close: {row['Close']:.2f}  Vol: {int(row['Volume']):,}"
            )

        # Summary
        first_close = hist["Close"].iloc[0]
        last_close = hist["Close"].iloc[-1]
        pct_change = ((last_close - first_close) / first_close) * 100 if first_close > 0 else 0
        lines.append("-" * 50)
        lines.append(f"Period Change: {pct_change:+.2f}% ({first_close:.2f} -> {last_close:.2f})")
        lines.append(f"High: {hist['High'].max():.2f} | Low: {hist['Low'].min():.2f}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"stock_history_tool error: {e}")
        return f"Error fetching stock history: {e}"


@function_tool
async def stock_info_tool(symbol: str) -> str:
    """
    Get company information for a stock ticker.
    Args:
        symbol: Stock ticker symbol (e.g. 'AAPL', 'MSFT').
    """
    try:
        if not YFINANCE_AVAILABLE:
            return "Error: yfinance is not installed. Run: pip install yfinance"

        symbol = symbol.upper().strip()

        def _fetch():
            ticker = yf.Ticker(symbol)
            return ticker.info

        info = await asyncio.to_thread(_fetch)

        if not info:
            return f"No info available for: {symbol}"

        lines = [f"Company Info: {symbol}", "=" * 50]

        fields = [
            ("Name", "shortName"),
            ("Sector", "sector"),
            ("Industry", "industry"),
            ("Country", "country"),
            ("Website", "website"),
            ("Employees", "fullTimeEmployees"),
            ("Market Cap", "marketCap"),
            ("PE Ratio (Trailing)", "trailingPE"),
            ("PE Ratio (Forward)", "forwardPE"),
            ("EPS (Trailing)", "trailingEps"),
            ("Dividend Yield", "dividendYield"),
            ("52-Week High", "fiftyTwoWeekHigh"),
            ("52-Week Low", "fiftyTwoWeekLow"),
            ("50-Day Avg", "fiftyDayAverage"),
            ("200-Day Avg", "twoHundredDayAverage"),
            ("Revenue", "totalRevenue"),
            ("Profit Margin", "profitMargins"),
        ]

        for label, key in fields:
            val = info.get(key)
            if val is not None:
                # Format large numbers
                if isinstance(val, (int, float)):
                    if key in ("marketCap", "totalRevenue") and val > 1_000_000:
                        if val >= 1e12:
                            val = f"${val / 1e12:.2f}T"
                        elif val >= 1e9:
                            val = f"${val / 1e9:.2f}B"
                        elif val >= 1e6:
                            val = f"${val / 1e6:.2f}M"
                    elif key in ("dividendYield", "profitMargins"):
                        val = f"{val * 100:.2f}%"
                    elif key == "fullTimeEmployees":
                        val = f"{val:,}"
                    elif isinstance(val, float):
                        val = f"{val:.2f}"
                lines.append(f"  {label}: {val}")

        # Business summary (truncated)
        summary = info.get("longBusinessSummary", "")
        if summary:
            truncated = summary[:300] + "..." if len(summary) > 300 else summary
            lines.append(f"\nBusiness Summary:\n  {truncated}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"stock_info_tool error: {e}")
        return f"Error fetching company info: {e}"


@function_tool
async def crypto_price_tool(symbol: str) -> str:
    """
    Get cryptocurrency price using CoinGecko free API.
    Args:
        symbol: Crypto name or id (e.g. 'bitcoin', 'ethereum', 'dogecoin', 'solana').
    """
    try:
        symbol = symbol.lower().strip()

        # CoinGecko free API (no key required)
        url = (
            f"https://api.coingecko.com/api/v3/coins/{symbol}"
            f"?localization=false&tickers=false&community_data=false&developer_data=false"
        )

        def _fetch():
            return _fetch_url_json(url, timeout=15)

        try:
            data = await asyncio.to_thread(_fetch)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Try search
                search_url = f"https://api.coingecko.com/api/v3/search?query={symbol}"
                search_data = await asyncio.to_thread(lambda: _fetch_url_json(search_url))
                coins = search_data.get("coins", [])
                if coins:
                    suggestions = ", ".join(c["id"] for c in coins[:5])
                    return f"Crypto '{symbol}' not found. Did you mean: {suggestions}?"
                return f"Crypto '{symbol}' not found on CoinGecko."
            raise

        market = data.get("market_data", {})
        name = data.get("name", symbol)
        sym = data.get("symbol", "").upper()

        price_usd = market.get("current_price", {}).get("usd", "N/A")
        change_24h = market.get("price_change_percentage_24h", 0)
        change_7d = market.get("price_change_percentage_7d", 0)
        market_cap = market.get("market_cap", {}).get("usd", 0)
        volume_24h = market.get("total_volume", {}).get("usd", 0)
        ath = market.get("ath", {}).get("usd", "N/A")
        atl = market.get("atl", {}).get("usd", "N/A")
        rank = data.get("market_cap_rank", "N/A")

        # Format market cap
        mc_str = "N/A"
        if market_cap:
            if market_cap >= 1e12:
                mc_str = f"${market_cap / 1e12:.2f}T"
            elif market_cap >= 1e9:
                mc_str = f"${market_cap / 1e9:.2f}B"
            elif market_cap >= 1e6:
                mc_str = f"${market_cap / 1e6:.2f}M"
            else:
                mc_str = f"${market_cap:,.0f}"

        vol_str = f"${volume_24h:,.0f}" if volume_24h else "N/A"

        lines = [
            f"Crypto: {name} ({sym})",
            f"Rank: #{rank}",
            f"Price: ${price_usd:,.6f}" if isinstance(price_usd, float) and price_usd < 1 else f"Price: ${price_usd:,.2f}" if isinstance(price_usd, (int, float)) else f"Price: {price_usd}",
            f"24h Change: {change_24h:+.2f}%",
            f"7d Change: {change_7d:+.2f}%",
            f"Market Cap: {mc_str}",
            f"24h Volume: {vol_str}",
            f"All-Time High: ${ath:,.2f}" if isinstance(ath, (int, float)) else f"ATH: {ath}",
            f"All-Time Low: ${atl:,.6f}" if isinstance(atl, (int, float)) and atl < 1 else f"All-Time Low: ${atl:,.2f}" if isinstance(atl, (int, float)) else f"ATL: {atl}",
        ]

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"crypto_price_tool error: {e}")
        return f"Error fetching crypto price: {e}"
