import asyncio
import os
import shutil
import glob
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    workspace_dir = Path("c:/Users/Administrator/Desktop/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main")
    port_file = workspace_dir / ".shell_electron_bridge_port"
    
    if not port_file.exists():
        print("Error: .shell_electron_bridge_port file not found!")
        return
        
    bridge_port = port_file.read_text(encoding="utf-8").strip()
    print(f"Read bridge port: {bridge_port}")
    
    artifacts_dir = Path("C:/Users/Administrator/.gemini/antigravity-ide/brain/0a274b89-dcc8-4ed8-9b61-0e7dc25a0e35")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    video_temp_dir = artifacts_dir / "temp_video"
    video_temp_dir.mkdir(parents=True, exist_ok=True)
    
    async with async_playwright() as p:
        print("Launching Chromium browser...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-web-security"]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(video_temp_dir)
        )
        
        # Inject window.electron to communicate with the live backend bridge
        print(f"Injecting window.electron bridge mapping to port {bridge_port}...")
        await context.add_init_script(f"""
            window.electron = {{
              ipcRenderer: {{
                invoke: async (channel, ...args) => {{
                  console.log('IPC Invoke:', channel, args);
                  
                  // Mock fallbacks for standard setup commands
                  if (channel === 'get-app-version') return '1.1.5';
                  if (channel === 'get-personality') return 'Aoede';
                  if (channel === 'get-settings') return {{}};
                  if (channel === 'offline-tts-status') return {{ success: true }};
                  if (channel === 'offline-llm-status') return {{ success: true }};
                  if (channel === 'offline-coding-llm-status') return {{ success: true }};
                  if (channel === 'secure-get-keys') return {{}};
                  if (channel === 'get-history') return [];
                  
                  try {{
                    const response = await fetch('http://127.0.0.1:{bridge_port}/call', {{
                      method: 'POST',
                      headers: {{ 'Content-Type': 'application/json' }},
                      body: JSON.stringify({{ channel, args: Array.isArray(args[0]) ? args[0] : args }})
                    }});
                    const data = await response.json();
                    console.log('IPC Response:', data);
                    return data.data !== undefined ? data.data : data;
                  }} catch (err) {{
                    console.error('IPC Error:', err);
                    return {{ success: false, error: err.message }};
                  }}
                }},
                on: (channel, callback) => {{
                  console.log('IPC On registered for', channel);
                }},
                off: (channel, callback) => {{
                  console.log('IPC Off unregistered for', channel);
                }},
                removeAllListeners: (channel) => {{
                  console.log('IPC removeAllListeners for', channel);
                }}
              }}
            }};
        """)
        
        page = await context.new_page()
        
        # Listen to console and errors
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER PAGE ERROR: {err}"))
        
        # Navigate to local built index.html matching Electron's file:// load
        local_url = "file:///c:/Users/Administrator/Desktop/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell_web_ui/dist/index.html?shell_host=electron&shell_perf=windows"
        print(f"Navigating to {local_url}...")
        await page.goto(local_url)
        await page.wait_for_timeout(5000)
        
        # Debugging: Take a screenshot of the page state before doing anything
        debug_screenshot = artifacts_dir / "connectors_debug_load.png"
        print(f"Saving debug load screenshot to {debug_screenshot}...")
        await page.screenshot(path=str(debug_screenshot))
        
        # Check what buttons are available
        buttons = await page.locator("button").all()
        print(f"Total buttons found: {len(buttons)}")
        for i, btn in enumerate(buttons):
            label = await btn.get_attribute("aria-label")
            text = await btn.text_content()
            safe_text = str(text or "").encode('ascii', errors='ignore').decode('ascii')
            safe_label = str(label or "").encode('ascii', errors='ignore').decode('ascii')
            print(f"Button {i}: label='{safe_label}', text='{safe_text}'")
            
        # Click SETTINGS tab
        print("Clicking Settings tab...")
        settings_button = page.locator("button[aria-label='Open SETTINGS view']")
        await settings_button.first.click()
        await page.wait_for_timeout(2000)
        
        # Click PLUGINS & CONNECTORS tab
        print("Clicking Plugins & Connectors tab...")
        connectors_tab = page.locator("button[aria-label='Open settings connectors tab']")
        await connectors_tab.first.click()
        await page.wait_for_timeout(2000)
        
        # Screenshot 1: Initial Grid View
        screenshot_initial = artifacts_dir / "connectors_initial.png"
        print(f"Saving initial connectors view screenshot to {screenshot_initial}...")
        await page.screenshot(path=str(screenshot_initial))
        
        # Type search keyword "gmail"
        print("Testing search filter...")
        search_input = page.locator("input[placeholder='Search plugins & connectors...']")
        await search_input.fill("gmail")
        await page.wait_for_timeout(1500)
        
        # Screenshot 2: Search filter
        screenshot_search = artifacts_dir / "connectors_search.png"
        print(f"Saving search connectors view screenshot to {screenshot_search}...")
        await page.screenshot(path=str(screenshot_search))
        
        # Clear search and click category buttons
        await search_input.fill("")
        await page.wait_for_timeout(500)
        
        # Click SOCIAL category filter to focus on Telegram and Instagram
        print("Clicking SOCIAL category filter...")
        social_button = page.locator("button:has-text('SOCIAL')")
        await social_button.first.click()
        await page.wait_for_timeout(1500)
            
        # Test Telegram Token Submission
        print("Testing Telegram connector card token input...")
        token_input = page.locator(".group:has-text('Telegram Bot') input")
        await token_input.first.fill("123456789:AAtestTokenValid")
        await page.wait_for_timeout(1000)
        
        # Screenshot 3: Token entry
        screenshot_token = artifacts_dir / "connectors_telegram_token.png"
        print(f"Saving token input connectors view screenshot to {screenshot_token}...")
        await page.screenshot(path=str(screenshot_token))
        
        # Click CONNECT BOT
        print("Clicking CONNECT BOT...")
        connect_button = page.locator(".group:has-text('Telegram Bot') button:has-text('CONNECT BOT')")
        await connect_button.first.click()
        
        # Wait for simulation of connection validation
        await page.wait_for_timeout(3500)
        
        # Screenshot 4: Post connection result
        screenshot_result = artifacts_dir / "connectors_result.png"
        print(f"Saving connection result screenshot to {screenshot_result}...")
        await page.screenshot(path=str(screenshot_result))
        
        # Switch to COMMUNICATION category filter for Gmail
        print("Clicking COMMUNICATION category filter...")
        comm_button = page.locator("button:has-text('COMMUNICATION')")
        await comm_button.first.click()
        await page.wait_for_timeout(1500)
        
        # Test Gmail redirect connect
        print("Clicking Gmail CONNECT ACCOUNT (triggering Selenium browser workflow)...")
        gmail_connect = page.locator(".group:has-text('Gmail API') button:has-text('CONNECT ACCOUNT')")
        if await gmail_connect.count() > 0:
            await gmail_connect.first.click()
            # Wait for backend thread to launch and update status
            await page.wait_for_timeout(4000)
            
            # Screenshot 5: Gmail Connecting redirect state
            screenshot_gmail = artifacts_dir / "connectors_gmail_redirect.png"
            print(f"Saving Gmail connecting state screenshot to {screenshot_gmail}...")
            await page.screenshot(path=str(screenshot_gmail))
            
        print("Closing browser context...")
        await context.close()
        await browser.close()
        
    # Locate the recorded video and save to artifacts directory
    video_files = glob.glob(str(video_temp_dir / "*.webm"))
    if video_files:
        latest_video = video_files[0]
        final_video_path = artifacts_dir / "shell_ui_walkthrough.webm"
        print(f"Copying recorded video to {final_video_path}...")
        shutil.copy(latest_video, final_video_path)
        
        # Cleanup temp video directory
        shutil.rmtree(video_temp_dir)
        print("Video cleanup complete.")
    else:
        print("Warning: No video recording file found!")
        
    print("Visual test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
