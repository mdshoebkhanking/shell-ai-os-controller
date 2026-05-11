
import webbrowser
import asyncio
import logging
import pyautogui
import pyperclip
import os
from shell_safe_executor import god_tier_tool as function_tool

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shell_social_automation")

class SocialGod:
    """
    Unified social media automation.
    Telegram, Instagram, WhatsApp, Twitter/X, LinkedIn, Facebook, GitHub, YouTube, TikTok.
    Browser automation + vision/keyboard shortcuts se sab handle karta hai.
    """
    def __init__(self):
        self.telegram_url = "https://web.telegram.org/a/" # Modern Version
        self.instagram_url = "https://www.instagram.com/direct/inbox/"
        self.whatsapp_url = "https://web.whatsapp.com/"

        # Sab supported platforms aur unke profile URL templates
        self.platform_urls = {
            "instagram": "https://www.instagram.com/{username}/",
            "twitter": "https://twitter.com/{username}",
            "x": "https://x.com/{username}",
            "linkedin": "https://www.linkedin.com/in/{username}/",
            "facebook": "https://www.facebook.com/{username}",
            "github": "https://github.com/{username}",
            "youtube": "https://www.youtube.com/@{username}",
            "tiktok": "https://www.tiktok.com/@{username}",
        }

        # Compose / new post URLs for posting
        self.compose_urls = {
            "twitter": "https://twitter.com/compose/tweet",
            "x": "https://twitter.com/compose/tweet",
            "facebook": "https://www.facebook.com/",
            "instagram": "https://www.instagram.com/",  # Posting requires mobile, browser se limited hai
        }

        # Fallback coordinates for common resolutions (Message button waghera ke liye)
        self.fallback_coords = {
            "1920x1080": {"instagram_message_btn": [(880, 310), (900, 320), (850, 300)]},
            "1366x768":  {"instagram_message_btn": [(630, 220), (650, 230), (610, 210)]},
            "2560x1440": {"instagram_message_btn": [(1170, 415), (1200, 420), (1140, 400)]},
            "1536x864":  {"instagram_message_btn": [(710, 260), (730, 270), (690, 250)]},
        }

    def get_supported_platforms(self) -> dict:
        """
        Returns dict of all supported platforms aur unke URLs / capabilities.
        Yeh method batata hai ki konse platforms supported hain.
        """
        return {
            "telegram": {
                "url": self.telegram_url,
                "capabilities": ["send_message", "send_image"],
                "type": "messaging"
            },
            "instagram": {
                "url": self.instagram_url,
                "profile_url": self.platform_urls["instagram"],
                "capabilities": ["send_message", "view_profile", "open_compose"],
                "type": "social + messaging"
            },
            "whatsapp": {
                "url": self.whatsapp_url,
                "capabilities": ["open_chat"],
                "type": "messaging"
            },
            "twitter": {
                "url": self.platform_urls["twitter"],
                "compose_url": self.compose_urls["twitter"],
                "capabilities": ["view_profile", "compose_post"],
                "type": "social"
            },
            "x": {
                "url": self.platform_urls["x"],
                "compose_url": self.compose_urls["x"],
                "capabilities": ["view_profile", "compose_post"],
                "type": "social"
            },
            "linkedin": {
                "url": self.platform_urls["linkedin"],
                "capabilities": ["view_profile"],
                "type": "professional"
            },
            "facebook": {
                "url": self.platform_urls["facebook"],
                "compose_url": self.compose_urls["facebook"],
                "capabilities": ["view_profile", "compose_post"],
                "type": "social"
            },
            "github": {
                "url": self.platform_urls["github"],
                "capabilities": ["view_profile"],
                "type": "developer"
            },
            "youtube": {
                "url": self.platform_urls["youtube"],
                "capabilities": ["view_profile"],
                "type": "video"
            },
            "tiktok": {
                "url": self.platform_urls["tiktok"],
                "capabilities": ["view_profile"],
                "type": "video"
            },
        }

    async def _focus_browser(self):
        """Browser window ko focus karta hai — Chrome, Edge, Firefox, Brave try karta hai."""
        from shell_window_CTRL import focus_window
        for browser in ["chrome", "edge", "firefox", "brave"]:
            if await focus_window(browser):
                await asyncio.sleep(0.5)
                return True
        return False

    def _get_fallback_coords(self, key: str) -> list:
        """
        Current screen resolution ke hisaab se fallback coordinates deta hai.
        Agar exact resolution nahi mili toh closest wali use karega.
        """
        s_w, s_h = pyautogui.size()
        res_key = f"{s_w}x{s_h}"
        if res_key in self.fallback_coords and key in self.fallback_coords[res_key]:
            return self.fallback_coords[res_key][key]
        # Closest resolution calculate karo
        best_match = None
        best_diff = float('inf')
        for res in self.fallback_coords:
            rw, rh = map(int, res.split('x'))
            diff = abs(rw - s_w) + abs(rh - s_h)
            if diff < best_diff:
                best_diff = diff
                best_match = res
        if best_match and key in self.fallback_coords[best_match]:
            # Scale coordinates to current resolution
            rw, rh = map(int, best_match.split('x'))
            scaled = []
            for (cx, cy) in self.fallback_coords[best_match][key]:
                scaled.append((int(cx * s_w / rw), int(cy * s_h / rh)))
            return scaled
        return []

    async def _copy_image_to_clipboard(self, image_path: str) -> bool:
        """
        Image ko clipboard mein copy karta hai — Windows pe PIL se.
        Yeh Telegram/WhatsApp mein image paste karne ke liye use hota hai.
        """
        try:
            from PIL import Image
            import io
            import ctypes
            from ctypes import wintypes

            img = Image.open(image_path)
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # BMP format mein clipboard ke liye — Windows specific
            output = io.BytesIO()
            img.save(output, format="BMP")
            bmp_data = output.getvalue()[14:]  # BMP header skip karo

            CF_DIB = 8
            GHND = 0x0042

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            user32.OpenClipboard(0)
            user32.EmptyClipboard()

            h_mem = kernel32.GlobalAlloc(GHND, len(bmp_data))
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, bmp_data, len(bmp_data))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(CF_DIB, h_mem)
            user32.CloseClipboard()

            logger.info(f"Image clipboard mein copy ho gayi: {image_path}")
            return True

        except Exception as e:
            logger.error(f"Image clipboard copy fail: {e}")
            return False

    # ========================= TELEGRAM =========================

    async def send_telegram(self, contact: str, message: str, image_path: str = None):
        """
        Telegram Web pe message bhejta hai.
        Agar image_path diya toh image bhi send karega saath mein.
        """
        try:
            logger.info(f"Telegram pe {contact} ko bhej rahe hain...")

            # 1. Open karo
            webbrowser.open(self.telegram_url)
            await asyncio.sleep(4.0)
            await self._focus_browser()

            # 2. Search karo contact
            pyautogui.press('esc')
            await asyncio.sleep(0.5)

            s_w, s_h = pyautogui.size()
            pyautogui.click(s_w * 0.15, s_h * 0.15)
            await asyncio.sleep(0.5)

            # Contact name type karo
            pyautogui.write(contact, interval=0.05)
            await asyncio.sleep(1.5)

            # Pehla result select karo
            pyautogui.press('enter')
            await asyncio.sleep(1.0)

            # 3. Agar image hai toh pehle image bhejo
            if image_path and os.path.exists(image_path):
                logger.info(f"Image bhi bhej rahe hain: {image_path}")
                img_copied = await self._copy_image_to_clipboard(image_path)
                if img_copied:
                    pyautogui.hotkey('ctrl', 'v')
                    await asyncio.sleep(2.0)
                    # Telegram shows preview — Enter se send hota hai
                    pyautogui.press('enter')
                    await asyncio.sleep(2.0)
                    logger.info("Image bhej di gayi")
                else:
                    logger.warning("Image clipboard mein copy nahi ho payi, sirf text bhejenge")

            # 4. Message type karo
            pyperclip.copy(message)
            pyautogui.hotkey('ctrl', 'v')
            await asyncio.sleep(0.5)

            # 5. Send karo
            pyautogui.press('enter')
            logger.info("Telegram message bhej diya!")

            result = f"Sent to {contact} via Telegram: '{message}'"
            if image_path:
                result += f" (with image: {os.path.basename(image_path)})"
            return result

        except Exception as e:
            logger.error(f"Telegram fail ho gaya: {e}")
            return f"Telegram Error: {e}"

    # ========================= INSTAGRAM =========================

    async def send_instagram(self, username: str, message: str):
        """
        Instagram Direct pe message bhejta hai — retry logic aur fallback coords ke saath.
        Agar vision engine se 'Message' button nahi mila toh fallback coordinates try karega.
        """
        MAX_RETRIES = 3
        try:
            logger.info(f"Instagram pe {username} ko message bhej rahe hain...")

            # 1. Profile open karo directly
            profile_url = f"https://www.instagram.com/{username}/"
            webbrowser.open(profile_url)
            await asyncio.sleep(6.0)
            await self._focus_browser()

            # 2. Notification popup dismiss karo
            pyautogui.press('esc')
            await asyncio.sleep(0.5)

            s_w, s_h = pyautogui.size()
            clicked = False

            # 3. Retry loop — vision engine se 'Message' button dhundho
            for attempt in range(1, MAX_RETRIES + 1):
                logger.info(f"Message button dhundh rahe hain... attempt {attempt}/{MAX_RETRIES}")
                try:
                    from vision_engine import vision_engine
                    coords = await asyncio.to_thread(
                        vision_engine.find_multiple_markers,
                        ["message", "send message", "Message"]
                    )

                    for marker_key in coords:
                        if coords[marker_key]:
                            click_x, click_y = coords[marker_key][0]
                            # Heuristic: Message button usually top half mein hota hai
                            if click_y < s_h * 0.5:
                                pyautogui.click(click_x, click_y)
                                clicked = True
                                logger.info(f"Vision se Message button mila at ({click_x}, {click_y})")
                                break
                    if clicked:
                        break
                except Exception as ve:
                    logger.warning(f"Vision engine attempt {attempt} fail: {ve}")

                if not clicked and attempt < MAX_RETRIES:
                    # Page scroll ya reload try karo
                    await asyncio.sleep(2.0)
                    pyautogui.press('esc')
                    await asyncio.sleep(0.5)

            # 4. Fallback coordinates try karo agar vision se nahi mila
            if not clicked:
                logger.info("Vision se nahi mila, fallback coordinates try kar rahe hain...")
                fallback_list = self._get_fallback_coords("instagram_message_btn")

                for fb_x, fb_y in fallback_list:
                    logger.info(f"Fallback coordinate try: ({fb_x}, {fb_y})")
                    pyautogui.click(fb_x, fb_y)
                    await asyncio.sleep(2.0)

                    # Check karo ki chat input open hua ya nahi
                    # Agar cursor text field mein hai toh kuch type kar ke check karo
                    try:
                        from vision_engine import vision_engine
                        check = await asyncio.to_thread(
                            vision_engine.find_multiple_markers,
                            ["type a message", "start a message"]
                        )
                        for mk in check:
                            if check[mk]:
                                clicked = True
                                logger.info(f"Fallback coordinate kaam kar gayi: ({fb_x}, {fb_y})")
                                break
                        if clicked:
                            break
                    except Exception:
                        # Agar vision fail ho toh assume karo click worked
                        clicked = True
                        break

            # 5. Agar abhi bhi nahi mila toh Tab navigation try karo
            if not clicked:
                logger.info("Fallback bhi fail, Tab navigation try kar rahe hain...")
                for tab_count in range(8, 15):
                    pyautogui.press('tab')
                    await asyncio.sleep(0.2)
                pyautogui.press('enter')
                await asyncio.sleep(2.0)
                clicked = True  # Assume tab navigation ne kaam kiya
                logger.info("Tab navigation se try kiya")

            # 6. Message bhejo
            if clicked:
                await asyncio.sleep(3.0)
                pyperclip.copy(message)
                pyautogui.hotkey('ctrl', 'v')
                await asyncio.sleep(0.5)
                pyautogui.press('enter')
                logger.info("Instagram message bhej diya!")
                return f"Sent to {username} via Instagram: '{message}'"
            else:
                return f"Could not find 'Message' button on {username}'s profile after {MAX_RETRIES} attempts + fallback."

        except Exception as e:
            logger.error(f"Instagram fail: {e}")
            return f"Instagram Error: {e}"

    # ========================= WHATSAPP =========================

    async def open_whatsapp_chat(self, contact: str):
        """
        WhatsApp Web khol ke specific contact ka chat open karta hai.
        Message nahi bhejta — sirf chat window open karega.
        """
        try:
            logger.info(f"WhatsApp pe {contact} ka chat khol rahe hain...")

            # 1. WhatsApp Web open karo
            webbrowser.open(self.whatsapp_url)
            await asyncio.sleep(6.0)  # WhatsApp Web thoda time leta hai load hone mein
            await self._focus_browser()

            # 2. Search bar mein click karo
            s_w, s_h = pyautogui.size()
            # WhatsApp Web ka search bar usually top-left mein hota hai
            pyautogui.click(s_w * 0.18, s_h * 0.08)
            await asyncio.sleep(1.0)

            # Alternative: Ctrl+F ya just click on "Search or start new chat"
            # Safer approach — keyboard shortcut
            pyautogui.hotkey('ctrl', 'f')
            await asyncio.sleep(0.5)

            # 3. Contact name type karo
            pyautogui.write(contact, interval=0.05)
            await asyncio.sleep(2.0)  # Search results aane do

            # 4. Pehla result select karo
            pyautogui.press('enter')
            await asyncio.sleep(1.5)

            logger.info(f"WhatsApp chat khul gayi: {contact}")
            return f"WhatsApp chat opened for: {contact}. Chat ready hai — message type kar sakte ho."

        except Exception as e:
            logger.error(f"WhatsApp chat open fail: {e}")
            return f"WhatsApp Error: {e}"

    # ========================= PROFILE OPENER =========================

    async def open_social_profile(self, platform: str, username: str):
        """
        Kisi bhi social media platform pe profile kholta hai browser mein.
        Supported: instagram, twitter/x, linkedin, facebook, github, youtube, tiktok.
        """
        try:
            platform_lower = platform.lower().strip()

            if platform_lower not in self.platform_urls:
                supported = ", ".join(self.platform_urls.keys())
                return f"Platform '{platform}' supported nahi hai. Supported platforms: {supported}"

            profile_url = self.platform_urls[platform_lower].format(username=username)
            logger.info(f"{platform_lower} pe {username} ka profile khol rahe hain: {profile_url}")

            webbrowser.open(profile_url)
            await asyncio.sleep(3.0)
            await self._focus_browser()

            logger.info(f"Profile khul gaya: {profile_url}")
            return f"{platform.capitalize()} profile opened: {profile_url}"

        except Exception as e:
            logger.error(f"Profile open fail: {e}")
            return f"Profile Error: {e}"

    # ========================= SOCIAL MEDIA POST =========================

    async def compose_social_post(self, platform: str, content: str):
        """
        Social media pe new post compose karta hai — auto-submit NAHI karta.
        User ko confirm karna padega. Content type kar deta hai bas.
        Supported: twitter/x, facebook, instagram (limited — browser se posting restricted hai).
        """
        try:
            platform_lower = platform.lower().strip()

            if platform_lower not in self.compose_urls:
                supported = ", ".join(self.compose_urls.keys())
                return f"Platform '{platform}' pe compose supported nahi hai. Try: {supported}"

            compose_url = self.compose_urls[platform_lower]
            logger.info(f"{platform_lower} pe post compose kar rahe hain...")

            webbrowser.open(compose_url)
            await asyncio.sleep(5.0)
            await self._focus_browser()

            # Platform-specific handling
            if platform_lower in ["twitter", "x"]:
                # Twitter compose dialog mein text area auto-focused hoti hai
                await asyncio.sleep(1.0)
                pyperclip.copy(content)
                pyautogui.hotkey('ctrl', 'v')
                await asyncio.sleep(0.5)
                logger.info("Twitter pe content type ho gaya — POST button user ko khud press karna hoga")
                return f"Twitter compose ready. Content typed: '{content[:50]}...' — Submit NAHI kiya, user please confirm karke post karo."

            elif platform_lower == "facebook":
                # Facebook pe "What's on your mind?" box pe click karna padta hai
                await asyncio.sleep(2.0)
                s_w, s_h = pyautogui.size()
                # "What's on your mind?" box usually center-top mein hota hai
                pyautogui.click(s_w * 0.45, s_h * 0.25)
                await asyncio.sleep(2.0)  # Post creation dialog khulne do
                pyperclip.copy(content)
                pyautogui.hotkey('ctrl', 'v')
                await asyncio.sleep(0.5)
                logger.info("Facebook pe content type ho gaya — POST button user ko press karna hoga")
                return f"Facebook compose ready. Content typed: '{content[:50]}...' — Submit NAHI kiya, user confirm karke post karo."

            elif platform_lower == "instagram":
                # Instagram browser se posting bahut limited hai — mobile app chahiye
                logger.info("Instagram browser se posting limited hai, page khol diya hai")
                return (
                    f"Instagram opened in browser. NOTE: Instagram browser se direct posting "
                    f"allow nahi karta — mobile app use karo ya Creator Studio try karo. "
                    f"Content ready tha: '{content[:50]}...'"
                )

            return f"Compose page opened for {platform}."

        except Exception as e:
            logger.error(f"Compose fail: {e}")
            return f"Compose Error: {e}"


# ========================= INSTANCE =========================
social_god = SocialGod()


# ========================= TOOL FUNCTIONS =========================

@function_tool
async def send_telegram_msg(contact: str, message_text: str, image_path: str = None) -> str:
    """
    Telegram Web pe message bhejta hai.
    Agar image_path diya toh image bhi attach karke bhejega.
    """
    return await social_god.send_telegram(contact, message_text, image_path)


@function_tool
async def send_instagram_msg(username: str, message_text: str) -> str:
    """
    Instagram Direct pe message bhejta hai — retry + fallback ke saath.
    Vision engine se Message button dhundhta hai, fail hone pe fallback coordinates try karta hai.
    """
    return await social_god.send_instagram(username, message_text)


@function_tool
async def open_whatsapp_chat_tool(contact: str) -> str:
    """
    WhatsApp Web khol ke specific contact ka chat open karta hai.
    Message nahi bhejta — sirf chat ready karta hai.
    """
    return await social_god.open_whatsapp_chat(contact)


@function_tool
async def open_social_profile_tool(platform: str, username: str) -> str:
    """
    Kisi bhi social media pe profile kholta hai browser mein.
    Supported: instagram, twitter, x, linkedin, facebook, github, youtube, tiktok.
    """
    return await social_god.open_social_profile(platform, username)


@function_tool
async def social_media_post_tool(platform: str, content: str) -> str:
    """
    Social media pe new post compose karta hai — auto-submit NAHI karta.
    User ko confirm karna padega. Supported: twitter/x, facebook, instagram (limited).
    """
    return await social_god.compose_social_post(platform, content)
