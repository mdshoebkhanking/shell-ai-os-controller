import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath("."))

from shell_offline_tts import speak_offline_tts

try:
    print("Testing speak_offline_tts...")
    res = speak_offline_tts("Haan bhai, main ready hoon.")
    print("Result:")
    # Remove process object from printing as it's not JSON serializable
    proc = res.pop("_process", None)
    print(json.dumps(res, indent=2))
    if proc:
        print("Playback started. Waiting for 3 seconds...")
        time.sleep(3.0)
        proc.terminate()
except Exception as e:
    print("Error calling speak_offline_tts:", e)
