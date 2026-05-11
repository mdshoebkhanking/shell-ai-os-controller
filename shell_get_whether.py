from shell_config import config
from shell_logger import get_logger
from shell_http import get_async_session, get_sync_session
from shell_cache import weather_cache
from shell_safe_executor import god_tier_tool as function_tool

logger = get_logger("shell_weather")

def detect_city_by_ip() -> str:
    """Sync helper — called rarely, OK to use sync session."""
    try:
        logger.info("IP se city detect karne ki koshish ho rahi hai")
        ip_info = get_sync_session().get("https://ipapi.co/json/", timeout=5).json()
        city = ip_info.get("city")
        if city:
            logger.info(f"IP se city detect kiya: {city}")
            return city
        else:
            logger.warning("City detect nahi hua, default 'Delhi' use ho raha hai")
            return "Delhi"
    except Exception as e:
        logger.error(f"IP se city detect mein error: {e}")
        return "Delhi"

@function_tool(rate_limit="weather_api")
async def get_weather(city: str = "") -> str:
    """
    Gets detailed current weather for a city including temperature, humidity, wind, visibility, pressure, sunrise/sunset.
    Args:
        city: City name (e.g., 'Mumbai', 'New York'). Auto-detects from IP if empty.
    """

    api_key = config.get_str("OPENWEATHER_API_KEY")

    if not api_key:
        logger.error("OpenWeather API key missing hai")
        return "OpenWeather API key nahi mili. .env check karo."

    if not city:
        city = detect_city_by_ip()

    # Check cache first
    cache_key = f"weather:{city.lower().strip()}"
    if weather_cache.has(cache_key):
        logger.info("Cache se weather data mila")
        return weather_cache.get(cache_key)

    logger.info(f"Weather fetch for: {city}")
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"
    }

    try:
        import aiohttp
        from datetime import datetime, timezone, timedelta
        session = await get_async_session()
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                body = await response.text()
                logger.error(f"OpenWeather API error: {response.status} - {body[:200]}")
                return f"Error: {city} ke liye weather fetch nahi ho paya. City name check karo."

            data = await response.json()
            # Schema guard — OpenWeather can return error responses or a
            # 200 with partial data; fail gracefully instead of KeyError.
            if not isinstance(data, dict) or "weather" not in data or "main" not in data:
                logger.error("Unexpected weather payload shape: %s", list(data.keys()) if isinstance(data, dict) else type(data).__name__)
                return f"Weather data format unexpected for '{city}'."
            weather_list = data.get("weather") or []
            if not weather_list or not isinstance(weather_list[0], dict):
                return f"Weather details missing for '{city}'."
            weather = weather_list[0].get("description", "Unknown").title()
            icon = _weather_icon(weather_list[0].get("main", ""))
            temp = data["main"].get("temp")
            if temp is None:
                return f"Weather temperature missing for '{city}'."
            feels_like = data["main"].get("feels_like", temp)
            temp_min = data["main"].get("temp_min", temp)
            temp_max = data["main"].get("temp_max", temp)
            humidity = data["main"]["humidity"]
            pressure = data["main"].get("pressure", 0)
            wind_speed = data["wind"]["speed"]
            wind_deg = data["wind"].get("deg", 0)
            visibility = data.get("visibility", 0) / 1000  # meters to km
            clouds = data.get("clouds", {}).get("all", 0)

            # Sunrise/Sunset
            tz_offset = data.get("timezone", 0)
            tz = timezone(timedelta(seconds=tz_offset))
            sunrise = datetime.fromtimestamp(data["sys"]["sunrise"], tz=tz).strftime("%I:%M %p")
            sunset = datetime.fromtimestamp(data["sys"]["sunset"], tz=tz).strftime("%I:%M %p")

            wind_dir = _wind_direction(wind_deg)

            result = (
                f"{icon} Weather in {city}:\n\n"
                f"  {weather}\n"
                f"  🌡️ Temperature: {temp}°C (feels like {feels_like}°C)\n"
                f"  📊 Min/Max: {temp_min}°C / {temp_max}°C\n"
                f"  💧 Humidity: {humidity}%\n"
                f"  🌬️ Wind: {wind_speed} m/s {wind_dir}\n"
                f"  👁️ Visibility: {visibility:.1f} km\n"
                f"  ☁️ Clouds: {clouds}%\n"
                f"  🔵 Pressure: {pressure} hPa\n"
                f"  🌅 Sunrise: {sunrise}\n"
                f"  🌇 Sunset: {sunset}"
            )

            logger.info(f"Weather result fetched for {city}")
            weather_cache.set(cache_key, result, ttl=600)
            return result

    except (asyncio.TimeoutError, TimeoutError):
        logger.warning("Weather API timeout")
        return "Weather request timeout ho gaya. Phir se try karo."
    except Exception as e:
        logger.exception(f"Weather fetch mein exception: {e}")
        return "Weather fetch mein error aaya"


@function_tool(rate_limit="weather_api")
async def get_weather_forecast(city: str = "", days: int = 3) -> str:
    """
    Gets weather forecast for upcoming days.
    Args:
        city: City name. Auto-detects from IP if empty.
        days: Number of days to forecast (1-5, default 3).
    """
    api_key = config.get_str("OPENWEATHER_API_KEY")
    if not api_key:
        return "OpenWeather API key nahi mili. .env check karo."

    if not city:
        city = detect_city_by_ip()

    days = max(1, min(5, days))

    cache_key = f"forecast:{city.lower().strip()}:{days}"
    if weather_cache.has(cache_key):
        return weather_cache.get(cache_key)

    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
        "cnt": days * 8  # 8 data points per day (3-hour intervals)
    }

    try:
        import aiohttp
        from datetime import datetime
        session = await get_async_session()
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status != 200:
                return f"Forecast error: {city} ke liye data nahi mila."

            data = await response.json()
            forecasts = data.get("list", [])

            if not forecasts:
                return "Forecast data nahi mila."

            result = f"📅 {days}-Day Forecast for {city}:\n\n"

            # Group by date
            daily = {}
            for item in forecasts:
                dt = datetime.fromtimestamp(item["dt"])
                date_str = dt.strftime("%a, %b %d")
                if date_str not in daily:
                    daily[date_str] = {
                        "temps": [],
                        "conditions": [],
                        "humidity": [],
                        "wind": []
                    }
                daily[date_str]["temps"].append(item["main"]["temp"])
                daily[date_str]["conditions"].append(item["weather"][0]["main"])
                daily[date_str]["humidity"].append(item["main"]["humidity"])
                daily[date_str]["wind"].append(item["wind"]["speed"])

            for date_str, info in list(daily.items())[:days]:
                avg_temp = sum(info["temps"]) / len(info["temps"])
                min_temp = min(info["temps"])
                max_temp = max(info["temps"])
                # Most common condition
                condition = max(set(info["conditions"]), key=info["conditions"].count)
                avg_humidity = sum(info["humidity"]) // len(info["humidity"])
                avg_wind = sum(info["wind"]) / len(info["wind"])
                icon = _weather_icon(condition)

                result += (
                    f"{icon} {date_str}:\n"
                    f"   {condition} | {min_temp:.0f}°C - {max_temp:.0f}°C (avg {avg_temp:.0f}°C)\n"
                    f"   💧 {avg_humidity}% | 🌬️ {avg_wind:.1f} m/s\n\n"
                )

            weather_cache.set(cache_key, result.strip(), ttl=1800)
            return result.strip()

    except Exception as e:
        logger.error(f"Forecast error: {e}")
        return f"Forecast fetch error: {e}"


@function_tool(rate_limit="weather_api")
async def get_air_quality(city: str = "") -> str:
    """
    Gets air quality index (AQI) for a city.
    Args:
        city: City name. Auto-detects from IP if empty.
    """
    api_key = config.get_str("OPENWEATHER_API_KEY")
    if not api_key:
        return "OpenWeather API key nahi mili."

    if not city:
        city = detect_city_by_ip()

    try:
        import aiohttp
        session = await get_async_session()

        # First get coordinates
        geo_url = "https://api.openweathermap.org/geo/1.0/direct"
        async with session.get(geo_url, params={"q": city, "appid": api_key, "limit": 1},
                               timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return f"City '{city}' nahi mili."
            geo = await resp.json()
            if not geo:
                return f"City '{city}' nahi mili."
            lat, lon = geo[0]["lat"], geo[0]["lon"]

        # Get air quality
        aqi_url = "https://api.openweathermap.org/data/2.5/air_pollution"
        async with session.get(aqi_url, params={"lat": lat, "lon": lon, "appid": api_key},
                               timeout=aiohttp.ClientTimeout(total=8)) as resp:
            if resp.status != 200:
                return "AQI data nahi mila."
            data = await resp.json()

        aqi_list = data.get("list", [])
        if not aqi_list:
            return "AQI data nahi mila."

        aqi = aqi_list[0]["main"]["aqi"]
        components = aqi_list[0].get("components", {})

        aqi_labels = {1: "Good 🟢", 2: "Fair 🟡", 3: "Moderate 🟠", 4: "Poor 🔴", 5: "Very Poor 🟣"}
        aqi_label = aqi_labels.get(aqi, f"Unknown ({aqi})")

        pm25 = components.get("pm2_5", 0)
        pm10 = components.get("pm10", 0)
        no2 = components.get("no2", 0)
        o3 = components.get("o3", 0)
        co = components.get("co", 0)
        so2 = components.get("so2", 0)

        result = (
            f"🌬️ Air Quality in {city}:\n\n"
            f"  AQI: {aqi_label}\n\n"
            f"  PM2.5: {pm25:.1f} µg/m³\n"
            f"  PM10: {pm10:.1f} µg/m³\n"
            f"  NO₂: {no2:.1f} µg/m³\n"
            f"  O₃: {o3:.1f} µg/m³\n"
            f"  CO: {co:.1f} µg/m³\n"
            f"  SO₂: {so2:.1f} µg/m³"
        )
        return result

    except Exception as e:
        logger.error(f"AQI error: {e}")
        return f"Air quality fetch error: {e}"


def _weather_icon(condition: str) -> str:
    """Returns emoji for weather condition."""
    icons = {
        "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
        "Thunderstorm": "⛈️", "Snow": "🌨️", "Mist": "🌫️", "Fog": "🌫️",
        "Haze": "🌫️", "Smoke": "💨", "Dust": "💨", "Tornado": "🌪️",
    }
    return icons.get(condition, "🌡️")


def _wind_direction(deg: int) -> str:
    """Converts wind degrees to compass direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return directions[idx]
