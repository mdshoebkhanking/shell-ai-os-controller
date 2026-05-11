"""
Shell Instagram Integration Module
-----------------------------------
Monitors Instagram accounts, fetches DMs, analyzes trends.
Uses instagrapi for robust API access and browser automation as backup.
"""

import os
import json
import time
import asyncio
import logging
import threading
from typing import Optional, Dict, List
from datetime import datetime
from pathlib import Path
from shell_safe_executor import god_tier_tool as function_tool

# Try importing instagrapi
try:
    from instagrapi import Client
    INSTAGRAPI_AVAILABLE = True
except ImportError:
    INSTAGRAPI_AVAILABLE = False

# Shell AI infrastructure
from shell_config import config
from shell_logger import get_logger

logger = get_logger("INSTAGRAM")

# User's Instagram accounts
PRIMARY_ACCOUNT = "@mdshoebkhanking2"
SECONDARY_ACCOUNT = "@mdshoebkhanking"

# Session storage
SESSION_FILE = "brain/data/instagram_session.json"
CACHE_FILE = "brain/data/instagram_cache.json"
REPLIED_COMMENTS_FILE = "brain/data/instagram_replied_comments.json"


def _load_replied_comments() -> set:
    """Load the set of comment IDs we have already replied to."""
    try:
        if os.path.exists(REPLIED_COMMENTS_FILE):
            with open(REPLIED_COMMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data.get("replied_ids", []))
    except Exception as e:
        logger.error(f"Error loading replied comments file: {e}")
    return set()


def _save_replied_comments(replied_ids: set):
    """Persist the set of replied comment IDs to disk."""
    try:
        os.makedirs(os.path.dirname(REPLIED_COMMENTS_FILE), exist_ok=True)
        with open(REPLIED_COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"replied_ids": list(replied_ids)}, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving replied comments file: {e}")


class ShellInstagramClient:
    """Wrapper for instagrapi Client with session management"""

    def __init__(self):
        self.client = None
        self.username = config.get_str("INSTAGRAM_USERNAME")
        self.password = config.get_str("INSTAGRAM_PASSWORD")

        if not INSTAGRAPI_AVAILABLE:
            logger.warning("⚠️ instagrapi not installed. Some features will be limited.")
            return

        self.client = Client()
        self.login()

    def login(self):
        """Login to Instagram and save session"""
        if not self.username or not self.password:
            logger.warning("❌ Instagram credentials not found in .env")
            return False

        try:
            # Try loading session
            if os.path.exists(SESSION_FILE):
                logger.info("Recycling Instagram session...")
                self.client.load_settings(SESSION_FILE)

            # Login
            logger.info(f"Logging in as {self.username}...")
            self.client.login(self.username, self.password)

            # Save session
            self.client.dump_settings(SESSION_FILE)
            logger.info("✅ Instagram Login Successful!")
            return True

        except Exception as e:
            logger.error(f"❌ Instagram Login Failed: {e}")
            return False

    def upload_reel(self, video_path: str, caption: str, hashtags: str = "", thumbnail_path: str = "") -> str:
        """Uploads a video as a Reel with optional hashtags and thumbnail."""
        if not self.client:
            return "❌ Instagram client not initialized."

        try:
            # Append hashtags to caption
            full_caption = caption
            if hashtags:
                tag_list = [t.strip() for t in hashtags.replace(",", " ").split() if t.strip()]
                formatted = " ".join(f"#{t.lstrip('#')}" for t in tag_list)
                full_caption = f"{caption}\n\n{formatted}"

            logger.info(f"Uploading Reel: {video_path}")

            # Build kwargs for clip_upload
            upload_kwargs: Dict = {
                "path": video_path,
                "caption": full_caption,
            }

            # Thumbnail generation / usage
            if thumbnail_path and os.path.exists(thumbnail_path):
                upload_kwargs["thumbnail"] = Path(thumbnail_path)
            else:
                # Attempt auto-thumbnail from first frame using ffmpeg
                try:
                    import subprocess
                    auto_thumb = video_path + "_thumb.jpg"
                    subprocess.run(
                        [
                            "ffmpeg", "-y", "-i", video_path,
                            "-vframes", "1", "-q:v", "2", auto_thumb,
                        ],
                        capture_output=True,
                        timeout=30,
                    )
                    if os.path.exists(auto_thumb):
                        upload_kwargs["thumbnail"] = Path(auto_thumb)
                        logger.info(f"Auto-generated thumbnail: {auto_thumb}")
                except Exception as thumb_err:
                    logger.warning(f"Thumbnail generation skipped: {thumb_err}")

            media = self.client.clip_upload(**upload_kwargs)
            return f"✅ Reel Uploaded Successfully! URL: https://www.instagram.com/reel/{media.code}/"
        except Exception as e:
            return f"❌ Upload Failed: {e}"

    def upload_photo(self, image_path: str, caption: str) -> str:
        """Uploads a photo post."""
        if not self.client:
            return "❌ Instagram client not initialized."

        try:
            logger.info(f"Uploading Photo: {image_path}")
            media = self.client.photo_upload(
                path=Path(image_path),
                caption=caption,
            )
            return f"✅ Photo Uploaded Successfully! URL: https://www.instagram.com/p/{media.code}/"
        except Exception as e:
            return f"❌ Photo Upload Failed: {e}"

    def get_profile_info(self, username: str = "") -> Dict:
        """Gets profile info for a user, or self if username is empty."""
        if not self.client:
            return {"error": "Instagram client not initialized."}

        try:
            if not username:
                username = self.username

            # Strip leading @ if present
            username = username.lstrip("@")
            user_info = self.client.user_info_by_username(username)

            return {
                "username": user_info.username,
                "full_name": user_info.full_name,
                "bio": user_info.biography,
                "follower_count": user_info.follower_count,
                "following_count": user_info.following_count,
                "post_count": user_info.media_count,
                "is_verified": user_info.is_verified,
                "is_private": user_info.is_private,
                "profile_pic_url": str(user_info.profile_pic_url),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_followers(self, count: int = 20) -> List[Dict]:
        """Gets a list of recent followers."""
        if not self.client:
            return []

        try:
            my_pk = self.client.user_id
            followers = self.client.user_followers(my_pk, amount=count)
            result = []
            for user_id, user_info in followers.items():
                result.append({
                    "username": user_info.username,
                    "full_name": user_info.full_name,
                })
            return result
        except Exception as e:
            logger.error(f"Error fetching followers: {e}")
            return []

    def get_unread_dms(self, limit: int = 10) -> List[Dict]:
        """Fetches pending thread requests and unread DMs"""
        if not self.client: return []

        dms = []
        try:
            # Check pending requests first (often where new DMs go)
            pending = self.client.direct_pending_inbox()
            for thread in pending:
                if not thread.users or not thread.messages:
                    continue
                msg = thread.messages[0]
                dms.append({
                    "id": thread.id,
                    "user": thread.users[0].username,
                    "message": msg.text if msg.text else "Media",
                    "timestamp": str(msg.timestamp) if hasattr(msg, "timestamp") and msg.timestamp else "",
                    "type": "pending"
                })

            # Check main inbox
            inbox = self.client.direct_threads(amount=limit)
            for thread in inbox:
                if not thread.users or not thread.messages:
                    continue
                # Simple logic: if last message is not from me, count as unread/relevant
                last_msg = thread.messages[0]
                if str(last_msg.user_id) != str(self.client.user_id):
                    dms.append({
                        "id": thread.id,
                        "user": thread.users[0].username,
                        "message": last_msg.text or "Media",
                        "timestamp": str(last_msg.timestamp) if hasattr(last_msg, "timestamp") and last_msg.timestamp else "",
                        "type": "inbox"
                    })
        except Exception as e:
            logger.error(f"Error fetching DMs: {e}")

        return dms[:limit]

    def reply_to_dm(self, thread_id: str, text: str) -> bool:
        """Replies to a DM thread"""
        if not self.client: return False
        try:
            self.client.direct_answer(thread_id, text)
            return True
        except Exception as e:
            logger.error(f"Reply Error: {e}")
            return False

    def reply_to_comment(self, media_id: str, comment_id: str, text: str):
        """Replies to a specific comment"""
        if not self.client: return
        self.client.media_comment(media_id, text, replied_to_comment_id=comment_id)

    def get_latest_media_comments(self) -> List[Dict]:
        """Get comments from latest media to auto-reply"""
        if not self.client: return []

        comments_data = []
        try:
            # Get latest post
            my_pk = self.client.user_id
            latest_media = self.client.user_medias(my_pk, amount=1)[0]

            # Get comments
            comments = self.client.media_comments(latest_media.id)
            for comment in comments:
                # Skip my own comments
                if str(comment.user.pk) == str(my_pk):
                    continue

                comments_data.append({
                    "media_id": latest_media.id,
                    "comment_id": comment.pk,
                    "user": comment.user.username,
                    "text": comment.text,
                    "timestamp": comment.created_at_utc
                })
        except Exception as e:
            logger.error(f"Error fetching comments: {e}")

        return comments_data


# Global Client Instance (thread-safe singleton)
_insta_client = None
_insta_lock = threading.Lock()

def get_client():
    global _insta_client
    if _insta_client is None:
        with _insta_lock:
            if _insta_client is None:
                _insta_client = ShellInstagramClient()
    return _insta_client


# ---------------------------------------------------------------------------
# EXISTING TOOLS (upgraded)
# ---------------------------------------------------------------------------

@function_tool
async def instagram_login_check() -> str:
    """Checks and performs Instagram login via instagrapi."""
    client = get_client()
    if client.client:
        return f"✅ Instagram Logged In as {client.username}"
    return "❌ Instagram Login Failed. Check .env credentials."


@function_tool
async def instagram_upload_reel(video_path: str, caption: str, hashtags: str = "", thumbnail_path: str = "") -> str:
    """
    Uploads a video file as an Instagram Reel with optional hashtags and thumbnail.
    Args:
        video_path: Absolute path to the video file
        caption: Caption for the reel
        hashtags: Space or comma separated hashtags (e.g. 'viral reels trending')
        thumbnail_path: Optional path to a custom thumbnail image. If empty, auto-generates from first frame.
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    if not os.path.exists(video_path):
        return f"❌ File not found: {video_path}"

    return client.upload_reel(video_path, caption, hashtags=hashtags, thumbnail_path=thumbnail_path)


@function_tool
async def instagram_check_dms(limit: int = 10) -> str:
    """
    Checks for new DMs and returns a summary with timestamps.
    Args:
        limit: Maximum number of DMs to fetch (default 10)
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    dms = client.get_unread_dms(limit=limit)
    if not dms:
        return "✅ No new DMs found."

    summary = "📩 **New Messages**:\n"
    for dm in dms:
        ts = f" [{dm['timestamp']}]" if dm.get("timestamp") else ""
        summary += f"- From @{dm['user']} ({dm['type']}){ts}: {dm['message']}\n"

    return summary


@function_tool
async def instagram_auto_reply_dms(reply_message: str) -> str:
    """
    Auto-replies to all fetched unread DMs.
    Args:
        reply_message: The message to send to all unread chats.
    """
    client = get_client()
    if not client.client: return "❌ Instagram client not active."

    dms = client.get_unread_dms()
    if not dms: return "✅ No DMs to reply to."

    count = 0
    for dm in dms:
        success = client.reply_to_dm(dm['id'], reply_message)
        if success:
            count += 1
            await asyncio.sleep(2)  # Anti-ban delay (non-blocking)

    return f"✅ Auto-replied to {count} DMs."


@function_tool
async def instagram_auto_reply_comments(reply_message: str) -> str:
    """
    Auto-replies to comments on the latest post with duplicate detection.
    Tracks replied comment IDs in a JSON file to avoid double-replying.
    Args:
        reply_message: The reply text (e.g., 'Thanks for watching!')
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    comments = client.get_latest_media_comments()
    if not comments:
        return "✅ No new comments to reply to."

    # Load already-replied comment IDs
    replied_ids = _load_replied_comments()

    count = 0
    skipped = 0
    for c in comments:
        comment_id_str = str(c["comment_id"])

        # Duplicate detection: skip if already replied
        if comment_id_str in replied_ids:
            skipped += 1
            continue

        try:
            client.reply_to_comment(c["media_id"], c["comment_id"], reply_message)
            replied_ids.add(comment_id_str)
            count += 1
            await asyncio.sleep(3)  # Anti-ban delay (non-blocking)
        except Exception as e:
            logger.error(f"Failed to reply to {c['user']}: {e}")

    # Persist updated set
    _save_replied_comments(replied_ids)

    return f"✅ Replied to {count} comments. Skipped {skipped} already-replied."


# ---------------------------------------------------------------------------
# NEW TOOLS
# ---------------------------------------------------------------------------

@function_tool
async def instagram_get_profile_info_tool(username: str = "") -> str:
    """
    Gets Instagram profile info for any user, or your own profile if username is empty.
    Shows: follower count, following count, post count, bio, full name, verified status, privacy.
    Args:
        username: Instagram username to look up (without @). Leave empty for your own profile.
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    info = client.get_profile_info(username)

    if "error" in info:
        return f"❌ Error: {info['error']}"

    lines = [
        f"👤 **Profile: @{info['username']}**",
        f"  Full Name: {info['full_name']}",
        f"  Bio: {info['bio']}",
        f"  Followers: {info['follower_count']}",
        f"  Following: {info['following_count']}",
        f"  Posts: {info['post_count']}",
        f"  Verified: {'Yes' if info['is_verified'] else 'No'}",
        f"  Private: {'Yes' if info['is_private'] else 'No'}",
    ]
    return "\n".join(lines)


@function_tool
async def instagram_get_followers_tool(count: int = 20) -> str:
    """
    Gets a list of your recent followers with username and full name.
    Args:
        count: Number of followers to fetch (default 20)
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    followers = client.get_followers(count=count)
    if not followers:
        return "✅ No followers found or unable to fetch."

    lines = [f"👥 **Your Followers ({len(followers)})**:"]
    for f in followers:
        name_part = f" ({f['full_name']})" if f.get("full_name") else ""
        lines.append(f"  - @{f['username']}{name_part}")

    return "\n".join(lines)


@function_tool
async def instagram_upload_photo_tool(image_path: str, caption: str) -> str:
    """
    Uploads a photo to Instagram as a regular post (not a reel).
    Args:
        image_path: Absolute path to the image file (jpg, png, webp)
        caption: Caption for the photo post
    """
    client = get_client()
    if not client.client:
        return "❌ Instagram client not active."

    if not os.path.exists(image_path):
        return f"❌ File not found: {image_path}"

    # Validate image extension
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
    ext = os.path.splitext(image_path)[1].lower()
    if ext not in valid_extensions:
        return f"❌ Invalid image format '{ext}'. Supported: {', '.join(sorted(valid_extensions))}"

    return client.upload_photo(image_path, caption)
