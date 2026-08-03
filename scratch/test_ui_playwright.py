import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        # Launch chromium with disabled web security to bypass CORS
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-web-security"]
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        
        # Add init script to inject window.electron
        await context.add_init_script("""
            window.electron = {
              ipcRenderer: {
                invoke: async (channel, ...args) => {
                  console.log('IPC Invoke:', channel, args);
                  
                  // Mock fallbacks for standard setup commands
                  if (channel === 'get-app-version') return '1.1.5';
                  if (channel === 'get-personality') return 'Aoede';
                  if (channel === 'get-settings') return {};
                  if (channel === 'offline-tts-status') return { success: true };
                  if (channel === 'offline-llm-status') return { success: true };
                  if (channel === 'offline-coding-llm-status') return { success: true };
                  if (channel === 'secure-get-keys') return {};
                  if (channel === 'get-history') return [];
                  
                  try {
                    const response = await fetch('http://127.0.0.1:50099/call', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ channel, args: Array.isArray(args[0]) ? args[0] : args })
                    });
                    const data = await response.json();
                    console.log('IPC Response:', data);
                    return data.data !== undefined ? data.data : data;
                  } catch (err) {
                    console.error('IPC Error:', err);
                    return { success: false, error: err.message };
                  }
                },
                on: (channel, callback) => {
                  console.log('IPC On registered for', channel);
                },
                off: (channel, callback) => {
                  console.log('IPC Off unregistered for', channel);
                },
                removeAllListeners: (channel) => {
                  console.log('IPC removeAllListeners for', channel);
                }
              }
            };
        """)
        
        page = await context.new_page()
        
        # Listen to console and errors
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"BROWSER PAGE ERROR: {err}"))
        
        # Navigate to web server
        print("Navigating to http://127.0.0.1:50088...")
        await page.goto("http://127.0.0.1:50088")
        await page.wait_for_timeout(3000)
        
        # Click SETTINGS tab
        print("Clicking Settings tab...")
        settings_button = page.locator("button[aria-label='Open SETTINGS view']")
        await settings_button.first.click()
        await page.wait_for_timeout(2000)
        
        # Click CONNECTORS tab
        print("Clicking Connectors tab...")
        connectors_tab = page.locator("button[aria-label='Open settings connectors tab']")
        await connectors_tab.first.click()
        await page.wait_for_timeout(1000)
        
        # Save screenshot
        artifacts_dir = r"C:\Users\Administrator\Desktop\shell.v1.0-main-main\shell.v1.0-main-main\shell.v1.0-main-main\shell.v1.0-main-main\shell.v1.0-main-main"
        initial_screenshot = os.path.join(artifacts_dir, "connectors_initial.png")
        print(f"Saving initial screenshot to {initial_screenshot}...")
        await page.screenshot(path=initial_screenshot)
        
        # Copy to appData artifacts directory for final user display
        appdata_artifacts_dir = r"C:\Users\Administrator\.gemini\antigravity-ide\brain\0a274b89-dcc8-4ed8-9b61-0e7dc25a0e35"
        os.makedirs(appdata_artifacts_dir, exist_ok=True)
        shutil_screenshot = os.path.join(appdata_artifacts_dir, "connectors_initial.png")
        await page.screenshot(path=shutil_screenshot)
        
        # In Telegram Bot card, let's connect
        print("Testing Telegram connection...")
        token_input = page.locator("input[placeholder='123456789:bot_token']")
        await token_input.fill("123:fake_token_for_test")
        
        # Click CONNECT BOT
        connect_button = page.locator("button:has-text('CONNECT BOT')")
        await connect_button.first.click()
        
        # Wait for API validation callback
        await page.wait_for_timeout(2000)
        
        # Save post-connection screenshot
        connected_screenshot = os.path.join(appdata_artifacts_dir, "connectors_connected.png")
        print(f"Saving post-connection screenshot to {connected_screenshot}...")
        await page.screenshot(path=connected_screenshot)
        
        await browser.close()
        print("Browser test completed successfully!")

if __name__ == "__main__":
    import shutil
    asyncio.run(main())
