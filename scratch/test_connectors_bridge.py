import sys
import os

# Add current working directory to sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "shell_web_ui"))

from host import ShellBackendBridge

def main():
    print("Initializing ShellBackendBridge...")
    bridge = ShellBackendBridge()
    
    print("\n--- Testing 'social-media-status' ---")
    status_res = bridge._dispatch("social-media-status", [])
    print("Status response:", status_res)
    
    print("\n--- Testing 'social-media-connect' for invalid platform ---")
    connect_res = bridge._dispatch("social-media-connect", [{"platform": "unknown"}])
    print("Invalid platform response:", connect_res)

    print("\n--- Testing 'social-media-connect' for telegram with empty token ---")
    connect_res2 = bridge._dispatch("social-media-connect", [{"platform": "telegram", "bot_token": ""}])
    print("Empty token response:", connect_res2)

    print("\n--- Testing 'social-media-disconnect' for telegram ---")
    disconnect_res = bridge._dispatch("social-media-disconnect", [{"platform": "telegram"}])
    print("Disconnect response:", disconnect_res)
    
    print("\nAll bridge basic tests completed!")

if __name__ == "__main__":
    main()
