"""
SHELL SUPERVISOR (The Guardian)
-------------------------------
Keeps the Agent alive indefinitely.
If Agent crashes -> Restarts it immediately.
"""

import subprocess
import time
import sys
import os
from shell_logger import get_logger

logger = get_logger("shell_supervisor")

def main():
    logger.info("[SUPERVISOR] GUARDING SHELL AGENT (PID: SELF)")

    restart_count = 0
    max_restarts = 100 # Effectively infinite for normal usage

    while True:
        try:
            logger.info(f"[SUPERVISOR] LAUNCHING AGENT (Attempt {restart_count+1})...")

            # Use the same python executable
            python_exe = sys.executable

            # Launch Agent
            process = subprocess.Popen([python_exe, "agent.py"])

            # Wait for it to finish (blocking)
            process.wait()

            # Check exit code
            if process.returncode != 0:
                logger.error(f"[CRASH DETECTED] Agent exited with code {process.returncode}.")
                logger.info("[SUPERVISOR] Restarting in 2 seconds...")
                time.sleep(2)
                restart_count += 1
            else:
                logger.info("[SHUTDOWN] Agent exited cleanly. Guardian signing off.")
                break

        except KeyboardInterrupt:
            logger.info("[SUPERVISOR] Hard Stop requested.")
            break
        except Exception as e:
            logger.error(f"[SUPERVISOR ERROR] {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
