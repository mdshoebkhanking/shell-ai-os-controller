import re
import json
import logging
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from shell_safe_executor import god_tier_tool as function_tool

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YOUTUBE_SUMMARY")


def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extracts the video ID from a YouTube URL.
    Supports various formats like watch?v=, youtu.be/, shorts/, embed/, live/, etc.
    """
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",   # Standard and embed
        r"youtu\.be\/([0-9A-Za-z_-]{11})",     # Shortened
        r"shorts\/([0-9A-Za-z_-]{11})",        # Shorts
        r"live\/([0-9A-Za-z_-]{11})",          # Live
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _get_youtube_api_key() -> Optional[str]:
    """Try to get YouTube Data API v3 key from shell_config."""
    try:
        from shell_config import config
        key = config.get_str("YOUTUBE_API_KEY", "") or config.get_str("GOOGLE_API_KEY", "")
        return key if key else None
    except Exception:
        return None


def _format_duration(seconds: int) -> str:
    """Convert seconds to human-readable duration."""
    if seconds < 0:
        return "Live / Unknown"
    h, remainder = divmod(int(seconds), 3600)
    m, s = divmod(remainder, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _parse_iso8601_duration(iso_dur: str) -> int:
    """Parse ISO 8601 duration like PT1H2M3S into total seconds."""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_dur)
    if not match:
        return 0
    h = int(match.group(1) or 0)
    m = int(match.group(2) or 0)
    s = int(match.group(3) or 0)
    return h * 3600 + m * 60 + s


async def _resolve_url(url: Optional[str]) -> str:
    """Resolve URL - use provided or auto-detect from browser."""
    if not url or "http" not in url:
        from shell_browser_CTRL import get_active_tab_url
        logger.info("Attempting auto-detection of current browser URL...")
        url = await get_active_tab_url()
    return url


async def _fetch_video_metadata_api(video_id: str, api_key: str) -> Optional[dict]:
    """Fetch video metadata using YouTube Data API v3."""
    import urllib.request
    import urllib.error

    try:
        api_url = (
            f"https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,contentDetails,statistics,liveStreamingDetails"
            f"&id={video_id}&key={api_key}"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "Shell-AI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        if not data.get("items"):
            return None

        item = data["items"][0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        live_details = item.get("liveStreamingDetails", {})

        duration_sec = _parse_iso8601_duration(content.get("duration", "PT0S"))
        is_live = snippet.get("liveBroadcastContent", "none") != "none"
        if is_live or live_details:
            is_live = True

        return {
            "title": snippet.get("title", "Unknown"),
            "channel": snippet.get("channelTitle", "Unknown"),
            "views": stats.get("viewCount", "N/A"),
            "likes": stats.get("likeCount", "N/A"),
            "comments_count": stats.get("commentCount", "N/A"),
            "duration_sec": duration_sec,
            "duration": _format_duration(duration_sec) if not is_live else "LIVE",
            "upload_date": snippet.get("publishedAt", "Unknown")[:10],
            "description": (snippet.get("description", "")[:500] or "No description"),
            "tags": snippet.get("tags", [])[:15],
            "is_live": is_live,
            "source": "YouTube Data API v3",
        }
    except Exception as e:
        logger.warning(f"YouTube Data API fetch failed: {e}")
        return None


async def _fetch_video_metadata_fallback(video_id: str) -> Optional[dict]:
    """Fetch video metadata using yt-dlp, youtube-dl, or pytube as fallback."""

    # Try yt-dlp first
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        duration_sec = info.get("duration") or 0
        is_live = info.get("is_live", False)
        return {
            "title": info.get("title", "Unknown"),
            "channel": info.get("uploader", info.get("channel", "Unknown")),
            "views": str(info.get("view_count", "N/A")),
            "likes": str(info.get("like_count", "N/A")),
            "comments_count": "N/A",
            "duration_sec": duration_sec,
            "duration": _format_duration(duration_sec) if not is_live else "LIVE",
            "upload_date": info.get("upload_date", "Unknown"),
            "description": (info.get("description", "")[:500] or "No description"),
            "tags": (info.get("tags") or [])[:15],
            "is_live": is_live,
            "source": "yt-dlp",
        }
    except Exception as e:
        logger.info(f"yt-dlp fallback failed: {e}")

    # Try pytube
    try:
        from pytube import YouTube as PyYouTube
        yt = PyYouTube(f"https://www.youtube.com/watch?v={video_id}")
        duration_sec = yt.length or 0
        return {
            "title": yt.title or "Unknown",
            "channel": yt.author or "Unknown",
            "views": str(yt.views) if yt.views else "N/A",
            "likes": "N/A",
            "comments_count": "N/A",
            "duration_sec": duration_sec,
            "duration": _format_duration(duration_sec),
            "upload_date": str(yt.publish_date)[:10] if yt.publish_date else "Unknown",
            "description": (yt.description or "")[:500] or "No description",
            "tags": (yt.keywords or [])[:15],
            "is_live": False,
            "source": "pytube",
        }
    except Exception as e:
        logger.info(f"pytube fallback failed: {e}")

    # Try youtube-dl (legacy)
    try:
        import youtube_dl
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        duration_sec = info.get("duration") or 0
        return {
            "title": info.get("title", "Unknown"),
            "channel": info.get("uploader", "Unknown"),
            "views": str(info.get("view_count", "N/A")),
            "likes": str(info.get("like_count", "N/A")),
            "comments_count": "N/A",
            "duration_sec": duration_sec,
            "duration": _format_duration(duration_sec),
            "upload_date": info.get("upload_date", "Unknown"),
            "description": (info.get("description", "")[:500] or "No description"),
            "tags": (info.get("tags") or [])[:15],
            "is_live": False,
            "source": "youtube-dl",
        }
    except Exception as e:
        logger.info(f"youtube-dl fallback failed: {e}")

    return None


async def _fetch_comments_api(video_id: str, count: int, api_key: str) -> Optional[list]:
    """Fetch top comments using YouTube Data API v3."""
    import urllib.request
    import urllib.error

    try:
        max_results = min(count, 100)
        api_url = (
            f"https://www.googleapis.com/youtube/v3/commentThreads"
            f"?part=snippet&videoId={video_id}"
            f"&maxResults={max_results}&order=relevance&textFormat=plainText"
            f"&key={api_key}"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "Shell-AI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        comments = []
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append({
                "author": snippet.get("authorDisplayName", "Unknown"),
                "text": snippet.get("textDisplay", ""),
                "likes": snippet.get("likeCount", 0),
                "replies": item["snippet"].get("totalReplyCount", 0),
            })
        return comments
    except Exception as e:
        logger.warning(f"YouTube Comments API failed: {e}")
        return None


async def _fetch_comments_fallback(video_id: str, count: int) -> Optional[list]:
    """Try to fetch comments using yt-dlp as fallback."""
    try:
        import yt_dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "getcomments": True,
            "extractor_args": {"youtube": {"max_comments": [str(count), "0", "0", "0"]}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

        raw_comments = info.get("comments") or []
        comments = []
        for c in raw_comments[:count]:
            comments.append({
                "author": c.get("author", "Unknown"),
                "text": c.get("text", ""),
                "likes": c.get("like_count", 0),
                "replies": 0,
            })
        # Sort by likes descending
        comments.sort(key=lambda x: x["likes"], reverse=True)
        return comments
    except Exception as e:
        logger.warning(f"yt-dlp comments fallback failed: {e}")
        return None


# ========================================================================================
# TOOL 1: GET VIDEO INFO (NEW)
# ========================================================================================

@function_tool
async def get_video_info_tool(url: str = "") -> str:
    """
    Gets YouTube video metadata (title, channel, views, likes, duration, upload date,
    description, tags) WITHOUT downloading or reading the transcript.
    If 'url' is not provided, auto-detects from the currently active browser tab.

    Args:
        url (str): The YouTube video URL. Leave empty to auto-detect from browser.
    """
    url = await _resolve_url(url)

    if "?" in url and "v=" not in url and "youtu.be" not in url:
        return "boss, ye koi valid YouTube video URL nahi lag raha. Kya aap ek video link de sakte hain?"

    video_id = extract_youtube_id(url)
    if not video_id:
        return (
            "boss, mujhe is URL se video ID extract nahi ho rahi.\n"
            "Valid formats: youtube.com/watch?v=XXX, youtu.be/XXX, youtube.com/shorts/XXX"
        )

    # Try YouTube Data API v3 first
    api_key = _get_youtube_api_key()
    metadata = None

    if api_key:
        logger.info("Fetching metadata via YouTube Data API v3...")
        metadata = await _fetch_video_metadata_api(video_id, api_key)

    if not metadata:
        logger.info("Trying fallback metadata extraction (yt-dlp/pytube/youtube-dl)...")
        metadata = await _fetch_video_metadata_fallback(video_id)

    if not metadata:
        return (
            "boss, maafi chahti hoon! Video ki info nikaalne mein problem ho gayi.\n"
            "Possible reasons:\n"
            "- YouTube API key set nahi hai (YOUTUBE_API_KEY ya GOOGLE_API_KEY .env mein daalein)\n"
            "- yt-dlp / pytube install nahi hai (pip install yt-dlp pytube)\n"
            "- Video private ya region-locked ho sakti hai\n"
            "- Network connectivity issue ho sakta hai"
        )

    # Format tags
    tags_str = ", ".join(metadata["tags"][:10]) if metadata["tags"] else "No tags available"

    # Format view/like counts
    def _fmt_count(val):
        try:
            n = int(val)
            if n >= 10_000_000:
                return f"{n / 1_000_000:.1f}M"
            elif n >= 100_000:
                return f"{n / 1_00_000:.1f}L"
            elif n >= 1_000:
                return f"{n / 1_000:.1f}K"
            return str(n)
        except (ValueError, TypeError):
            return str(val)

    live_badge = " [LIVE/PREMIERE]" if metadata.get("is_live") else ""

    result = (
        f"--- VIDEO INFO ---{live_badge}\n"
        f"Title      : {metadata['title']}\n"
        f"Channel    : {metadata['channel']}\n"
        f"Views      : {_fmt_count(metadata['views'])}\n"
        f"Likes      : {_fmt_count(metadata['likes'])}\n"
        f"Duration   : {metadata['duration']}\n"
        f"Uploaded   : {metadata['upload_date']}\n"
        f"Tags       : {tags_str}\n"
        f"--- Description (first 500 chars) ---\n"
        f"{metadata['description']}\n"
        f"--- END VIDEO INFO ---\n"
        f"(Source: {metadata['source']})"
    )
    return result


# ========================================================================================
# TOOL 2: GET VIDEO COMMENTS (NEW)
# ========================================================================================

@function_tool
async def get_video_comments_tool(url: str = "", count: int = 10) -> str:
    """
    Gets top comments from a YouTube video sorted by relevance/likes.
    Shows commenter name, comment text, like count, and reply count.
    If 'url' is not provided, auto-detects from the currently active browser tab.

    Args:
        url (str): The YouTube video URL. Leave empty to auto-detect from browser.
        count (int): Number of top comments to fetch (default 10, max 100).
    """
    url = await _resolve_url(url)

    video_id = extract_youtube_id(url)
    if not video_id:
        return (
            "boss, mujhe is URL se video ID extract nahi ho rahi.\n"
            "Ek valid YouTube video link dijiye (youtube.com/watch?v=XXX ya youtu.be/XXX)"
        )

    count = max(1, min(int(count), 100))

    # Try YouTube Data API v3 first
    api_key = _get_youtube_api_key()
    comments = None

    if api_key:
        logger.info("Fetching comments via YouTube Data API v3...")
        comments = await _fetch_comments_api(video_id, count, api_key)

    if not comments:
        logger.info("Trying yt-dlp fallback for comments...")
        comments = await _fetch_comments_fallback(video_id, count)

    if comments is None:
        return (
            "boss, comments fetch karne mein problem ho gayi.\n"
            "Possible reasons:\n"
            "- Video ke comments disabled hain\n"
            "- YouTube API key set nahi hai (YOUTUBE_API_KEY ya GOOGLE_API_KEY .env mein)\n"
            "- yt-dlp install nahi hai (pip install yt-dlp)\n"
            "- Video private ya age-restricted ho sakti hai"
        )

    if len(comments) == 0:
        return "boss, is video par koi comment nahi mila. Shayad comments disabled hain ya video bahut nayi hai."

    # Format output
    lines = [f"--- TOP {len(comments)} COMMENTS ---"]
    for i, c in enumerate(comments, 1):
        # Truncate very long comments for readability
        text = c["text"]
        if len(text) > 300:
            text = text[:300] + "..."
        lines.append(
            f"\n[{i}] {c['author']}\n"
            f"    {text}\n"
            f"    Likes: {c['likes']}  |  Replies: {c['replies']}"
        )
    lines.append("\n--- END COMMENTS ---")
    return "\n".join(lines)


# ========================================================================================
# TOOL 3: VIDEO SUMMARY (UPGRADED)
# ========================================================================================

@function_tool
async def video_summary_tool(url: Optional[str] = None, lang: str = "auto") -> str:
    """
    Extracts the transcript/content of a YouTube video or podcast for summarization.
    Shows video title, duration, word count at the top.
    If 'url' is not provided, it will attempt to detect the currently active browser tab URL.

    Args:
        url (Optional[str]): The YouTube URL (if found in message).
        lang (str): Language preference for transcript. Use 'auto' (default) to try hi, ur, en.
                    Or specify like 'en', 'hi', 'es', 'fr', etc.
    """
    url = await _resolve_url(url)

    if "?" in str(url) and "v=" not in str(url) and "youtu.be" not in str(url):
        return "boss, ye YouTube ka search page lag raha hai. Summary ke liye pehle koi video open kijiye!"

    video_id = extract_youtube_id(str(url))
    if not video_id:
        return (
            "boss, mujhe video ka link detect karne mein problem ho rahi hai.\n"
            "Kya aap message mein ek valid YouTube link de sakte hain?\n"
            "Supported formats: youtube.com/watch?v=XXX, youtu.be/XXX, youtube.com/shorts/XXX"
        )

    # Determine language list
    if lang == "auto":
        lang_list = ["hi", "ur", "en"]
    else:
        lang_list = [lang, "en"]  # User's choice + English fallback

    # Fetch video metadata for title/duration header
    header_info = ""
    try:
        api_key = _get_youtube_api_key()
        metadata = None
        if api_key:
            metadata = await _fetch_video_metadata_api(video_id, api_key)
        if not metadata:
            metadata = await _fetch_video_metadata_fallback(video_id)

        if metadata:
            is_live = metadata.get("is_live", False)
            if is_live:
                header_info = (
                    f"Title    : {metadata['title']}\n"
                    f"Channel  : {metadata['channel']}\n"
                    f"Duration : LIVE / PREMIERE\n"
                    f"NOTE     : Ye ek live/premiere video hai. Transcript limited ya unavailable ho sakta hai.\n"
                )
            else:
                header_info = (
                    f"Title    : {metadata['title']}\n"
                    f"Channel  : {metadata['channel']}\n"
                    f"Duration : {metadata['duration']}\n"
                )
    except Exception as e:
        logger.info(f"Could not fetch metadata for header: {e}")
        header_info = f"Video ID : {video_id}\n"

    # Fetch transcript
    try:
        logger.info(f"Fetching transcript for video ID: {video_id} (langs: {lang_list})")

        full_text = None

        # UTILITY: Handle different library versions
        if hasattr(YouTubeTranscriptApi, 'get_transcript'):
            transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=lang_list)
            full_text = " ".join([t['text'] for t in transcript_data])

        elif hasattr(YouTubeTranscriptApi, 'list_transcripts'):
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript = transcript_list.find_transcript(lang_list)
            full_text = " ".join([t['text'] for t in transcript.fetch()])

        elif hasattr(YouTubeTranscriptApi, 'list'):
            logger.info("Using legacy INSTANCE method (YouTubeTranscriptApi().fetch)")
            try:
                api = YouTubeTranscriptApi()
                transcript_data = api.fetch(video_id)
                full_text = " ".join([t.text for t in transcript_data])
            except Exception as e:
                logger.error(f"Instance fetch failed: {e}")
                transcript_list = YouTubeTranscriptApi.list(video_id)
                transcript = next(iter(transcript_list))
                full_text = " ".join([t['text'] for t in transcript.fetch()])
        else:
            raise AttributeError("Unknown YouTubeTranscriptApi method structure")

        if not full_text or len(full_text.strip()) == 0:
            return (
                f"{header_info}"
                "boss, transcript toh mila lekin wo khali hai.\n"
                "Video mein shayad sirf music/visuals hain aur koi speech nahi hai."
            )

        # Word count
        word_count = len(full_text.split())

        # Truncate if needed
        truncated = False
        if len(full_text) > 20000:
            full_text = full_text[:20000]
            truncated = True

        result = (
            f"--- VIDEO TRANSCRIPT ---\n"
            f"{header_info}"
            f"Words    : {word_count:,}\n"
            f"Language : {', '.join(lang_list)}\n"
            f"--- CONTENT START ---\n"
            f"{full_text}\n"
        )
        if truncated:
            result += "... [Transcript Truncated - bahut lamba tha]\n"
        result += "--- CONTENT END ---"
        return result

    except Exception as e:
        error_str = str(e).lower()
        logger.warning(f"API Transcript fetch failed: {e}")

        # Provide specific error messages
        if "disabled" in error_str:
            specific_msg = (
                f"{header_info}"
                "boss, is video ka transcript/subtitles creator ne disable kar rakha hai.\n"
                "Ye video transcript ke bina summarize nahi ho sakti through API."
            )
        elif "no transcript" in error_str or "not found" in error_str or "could not find" in error_str:
            specific_msg = (
                f"{header_info}"
                f"boss, is video mein '{', '.join(lang_list)}' language ka transcript available nahi hai.\n"
                f"Aap doosri language try kar sakte hain: video_summary_tool(lang='en') ya lang='es' etc."
            )
        elif "video unavailable" in error_str or "private" in error_str:
            specific_msg = (
                f"boss, ye video unavailable ya private hai. Transcript nikalna possible nahi hai."
            )
        elif "too many requests" in error_str or "429" in error_str:
            specific_msg = (
                f"{header_info}"
                "boss, YouTube API ne rate-limit kar diya hai. Thodi der baad try kijiye."
            )
        else:
            specific_msg = (
                f"{header_info}"
                f"boss, transcript fetch karne mein error aaya: {e}\n"
                "Ab vision fallback try kar rahi hoon..."
            )
            # Only try vision fallback for non-specific errors
            logger.info("Trying Vision Fallback...")
            return specific_msg + "\n" + await vision_summary_fallback()

        return specific_msg


# ========================================================================================
# VISION FALLBACK (kept from original)
# ========================================================================================

async def vision_summary_fallback() -> str:
    """Fallback mechanism using Clipboard and Full Screen OCR if API fails."""
    from shell_browser_CTRL import get_clipboard_text, read_screen_transcript, open_youtube_transcript
    import asyncio

    # 1. Try Clipboard (Extension auto-copy)
    clip_text = await get_clipboard_text()
    if "?" not in clip_text:
        logger.info("Content retrieved from Clipboard.")
        return f"--- CLIPBOARD CONTENT START ---\n{clip_text}\n--- CLIPBOARD CONTENT END ---"

    # 2. Attempt to OPEN Transcript Panel via Visual UI Interaction
    logger.info("Attempting to visually open Transcript panel...")
    open_status = await open_youtube_transcript()
    if "?" in open_status:
        logger.info("Transcript panel opened visually. Waiting for UI update...")
        await asyncio.sleep(2.0)  # Wait for panel to render
    else:
        logger.warning(f"Could not open transcript panel: {open_status}")

    # 3. Try Full Screen OCR dump
    screen_dump = await read_screen_transcript()
    if "?" not in screen_dump:
        logger.info("Content retrieved via Screen OCR.")
        return f"--- SCREEN OCR DATA START ---\n{screen_dump}\n--- SCREEN OCR DATA END ---\n(boss, maine screen se text scan kiya hai. Please is dump mein se transcript dhoondh kar summarize kariye.)"

    return "boss, maafi chahti hoon par na toh AI system kaam kar raha hai aur na hi screen par koi text mil raha hai. Kya aapne transcript panel ya extension open kiya hai?"
