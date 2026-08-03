import asyncio
import os
import shutil
import glob
import subprocess
import time
from pathlib import Path
from playwright.async_api import async_playwright

async def run_processes(env):
    workspace_dir = Path("c:/Users/Administrator/Desktop/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main")
    # Clean up old port hints
    for file in [".shell_hub_port", ".shell_electron_bridge_port"]:
        p = workspace_dir / file
        if p.exists():
            p.unlink()

    # Start hub
    print("Starting shell_hub.py...")
    hub_proc = subprocess.Popen(
        [".shellai_venv/Scripts/python", "shell_hub.py"],
        cwd=str(workspace_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait for .shell_hub_port to be written
    hub_port_file = workspace_dir / ".shell_hub_port"
    for _ in range(30):
        if hub_port_file.exists() and hub_port_file.read_text().strip():
            break
        await asyncio.sleep(0.5)
    else:
        # Check if process died
        if hub_proc.poll() is not None:
            stdout, _ = hub_proc.communicate()
            raise RuntimeError(f"shell_hub.py exited early. Output:\n{stdout}")
        raise RuntimeError("shell_hub.py did not write .shell_hub_port file.")
    
    hub_port = hub_port_file.read_text().strip()
    print(f"shell_hub.py started on port: {hub_port}")

    # Start bridge
    print("Starting shell_electron_bridge.py...")
    bridge_proc = subprocess.Popen(
        [".shellai_venv/Scripts/python", "shell_electron_bridge.py", "--port", "0"],
        cwd=str(workspace_dir),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait for .shell_electron_bridge_port
    bridge_port_file = workspace_dir / ".shell_electron_bridge_port"
    for _ in range(30):
        if bridge_port_file.exists() and bridge_port_file.read_text().strip():
            break
        await asyncio.sleep(0.5)
    else:
        if bridge_proc.poll() is not None:
            stdout, _ = bridge_proc.communicate()
            raise RuntimeError(f"shell_electron_bridge.py exited early. Output:\n{stdout}")
        raise RuntimeError("shell_electron_bridge.py did not write .shell_electron_bridge_port file.")

    bridge_port = bridge_port_file.read_text().strip()
    print(f"shell_electron_bridge.py started on port: {bridge_port}")
    
    return hub_proc, bridge_proc, hub_port, bridge_port

async def stop_processes(hub_proc, bridge_proc):
    print("Stopping backend processes...")
    for proc in [hub_proc, bridge_proc]:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

async def test_mode(mode_name, env_overrides, expected_reply_marker):
    # Prepare environment
    env = os.environ.copy()
    for k, v in env_overrides.items():
        env[k] = v
        
    hub_proc, bridge_proc, hub_port, bridge_port = await run_processes(env)
    
    artifacts_dir = Path("C:/Users/Administrator/.gemini/antigravity-ide/brain/0a274b89-dcc8-4ed8-9b61-0e7dc25a0e35")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            print(f"[{mode_name}] Launching Chromium...")
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-web-security"]
            )
            
            context = await browser.new_context(viewport={"width": 1280, "height": 800})
            
            # Inject window.electron to communicate with the live backend bridge and pipe events
            print(f"[{mode_name}] Injecting window.electron bridge mapping to port {bridge_port}...")
            voice_runtime_val = "gemini" if mode_name == "ONLINE" else "backend"
            await context.add_init_script(f"""
                localStorage.setItem('shell_voice_runtime', '{voice_runtime_val}');
                const listeners = {{}};
                window.electron = {{
                  ipcRenderer: {{
                    invoke: async (channel, ...args) => {{
                      console.log('IPC Invoke:', channel, args);
                      
                      // Mock fallbacks for standard setup commands
                      if (channel === 'get-app-version') return '1.1.5';
                      if (channel === 'get-personality') return 'Aoede';
                      if (channel === 'get-settings') return {{}};
                      if (channel === 'set-settings') return {{ success: true }};
                      if (channel === 'offline-tts-status') return {{ success: true }};
                      if (channel === 'offline-llm-status') return {{ success: true }};
                      if (channel === 'offline-coding-llm-status') return {{ success: true }};
                      if (channel === 'secure-get-keys') return {{}};
                      
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
                      if (!listeners[channel]) listeners[channel] = [];
                      listeners[channel].push(callback);
                    }},
                    off: (channel, callback) => {{
                      console.log('IPC Off unregistered for', channel);
                      if (!listeners[channel]) return;
                      listeners[channel] = listeners[channel].filter(cb => cb !== callback);
                    }},
                    removeAllListeners: (channel) => {{
                      console.log('IPC removeAllListeners for', channel);
                      delete listeners[channel];
                    }}
                  }}
                }};

                async function startEventStream() {{
                  console.log('Starting event stream subscription to bridge...');
                  try {{
                    const response = await fetch('http://127.0.0.1:{bridge_port}/events');
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    while (true) {{
                      const {{ value, done }} = await reader.read();
                      if (done) break;
                      buffer += decoder.decode(value, {{ stream: true }});
                      const packets = buffer.split('\\n\\n');
                      buffer = packets.pop() || '';
                      for (const packet of packets) {{
                        const line = packet.split('\\n').find(item => item.startsWith('data: '));
                        if (!line) continue;
                        try {{
                          const eventObj = JSON.parse(line.slice(6));
                          console.log('Bridge Event Received:', eventObj);
                          const channelListeners = listeners[eventObj.channel];
                          if (channelListeners) {{
                            for (const cb of channelListeners) {{
                              cb({{ channel: eventObj.channel }}, eventObj.payload);
                            }}
                          }}
                        }} catch (e) {{
                          console.error('Failed to parse bridge event:', e);
                        }}
                      }}
                    }}
                  }} catch (err) {{
                    console.error('Event stream connection failed:', err);
                    setTimeout(startEventStream, 1500);
                  }}
                }}
                
                // Let the browser load completely before launching stream
                window.addEventListener('DOMContentLoaded', () => {{
                  startEventStream();
                }});
            """)
            
            page = await context.new_page()
            
            # Listen to console and errors
            page.on("console", lambda msg: print(f"[{mode_name} BROWSER] {msg.type}: {msg.text}"))
            page.on("pageerror", lambda err: print(f"[{mode_name} BROWSER ERROR] {err}"))
            
            # Navigate to local built index.html matching Electron's file:// load
            local_url = "file:///c:/Users/Administrator/Desktop/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell.v1.0-main-main/shell_web_ui/dist/index.html?shell_host=electron&shell_perf=windows"
            print(f"[{mode_name}] Navigating to {local_url}...")
            await page.goto(local_url)
            await page.wait_for_timeout(5000)
            
            # Screenshot of main Dashboard load
            initial_ss = artifacts_dir / f"chat_{mode_name.lower()}_initial.png"
            await page.screenshot(path=str(initial_ss))
            print(f"[{mode_name}] Saved initial screen to {initial_ss}")
            
            # Locate input box by aria-label "Shell command input"
            chat_input = page.locator("input[aria-label='Shell command input']")
            # Type command
            query = "Explain quantum physics in one sentence."
            print(f"[{mode_name}] Typing query: '{query}'")
            await chat_input.fill(query)
            await page.wait_for_timeout(500)
            
            # Click SEND button
            send_btn = page.locator("button[aria-label='Send transcript message']")
            await send_btn.click()
            print(f"[{mode_name}] Clicked send")
            
            # Wait for response (up to 15 seconds)
            print(f"[{mode_name}] Waiting for reply to appear...")
            
            reply_found = False
            for _ in range(30):
                await page.wait_for_timeout(500)
                body_text = await page.inner_text("body")
                if expected_reply_marker.lower() in body_text.lower():
                    print(f"[{mode_name}] Success: Found expected reply containing '{expected_reply_marker}'")
                    reply_found = True
                    break
            
            if not reply_found:
                print(f"[{mode_name}] Warning: No reply matched in page text.")
            
            # Save final screenshot
            final_ss = artifacts_dir / f"chat_{mode_name.lower()}_response.png"
            await page.screenshot(path=str(final_ss))
            print(f"[{mode_name}] Saved final screen to {final_ss}")
            
            await browser.close()
    finally:
        await stop_processes(hub_proc, bridge_proc)

async def main():
    # 1. Test Online Mode (Forced Online)
    print("\n--- PHASE 1: TESTING FORCED ONLINE MODE ---")
    await test_mode("ONLINE", {
        "SHELL_TEST_FORCE_ONLINE": "1",
        "SHELL_TEST_FORCE_OFFLINE": "0",
        "SHELL_CHAT_MODE": "online",
        "SHELL_VOICE_MODE": "cloud",
        "GOOGLE_API_KEY": "AIzaSyDummyKeyForVisualTesting",
        "SHELL_CHAT_ONLINE_CHECK": "0",
        "SHELL_TEST_MOCK_ONLINE_REPLY": "I am Shell AI, your online cloud assistant powered by Gemini."
    }, "powered by Gemini")
    
    # 2. Test Offline Mode (Forced Offline)
    print("\n--- PHASE 2: TESTING FORCED OFFLINE MODE ---")
    await test_mode("OFFLINE", {
        "SHELL_TEST_FORCE_ONLINE": "0",
        "SHELL_TEST_FORCE_OFFLINE": "1",
        "SHELL_CHAT_MODE": "offline",
        "SHELL_VOICE_MODE": "local"
    }, "local mode")

if __name__ == "__main__":
    asyncio.run(main())
