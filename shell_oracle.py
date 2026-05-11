"""
SHELL ORACLE (Project Singularity)
----------------------------------
The Prophet Module.
Makes the AI PROACTIVE.
- Monitors System Health (CPU, RAM, Battery)
- Watches Network for Intruders
- Speaks autonomously when needed.
"""

import time
import os
import psutil
import threading
import logging
import asyncio
import random
from shell_system_god import system_god

logger = logging.getLogger("oracle")

class Oracle:
    def __init__(self, agent_session=None):
        self.running = False
        self.session = agent_session
        self.last_net_scan = 0
        self.known_devices = set()
        self.alert_queue = []
        self.net_scan_enabled = self._env_bool("SHELL_ORACLE_NET_SCAN", False)
        self.net_scan_interval_s = self._env_float("SHELL_ORACLE_NET_SCAN_INTERVAL_S", 900.0)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _env_float(name: str, default: float) -> float:
        try:
            return max(60.0, float(os.environ.get(name, default)))
        except Exception:
            return default

    def start(self, session):
        """Ignites the Oracle Eye."""
        if not self._env_bool("SHELL_ORACLE_ENABLED", True):
            logger.info("Oracle proactive monitor disabled by SHELL_ORACLE_ENABLED=0.")
            return
        if self.running:
            logger.info("Oracle proactive monitor already running; start ignored.")
            return
        self.session = session
        self.running = True
        logger.info("Oracle proactive monitor online.")
        
        # Start Background Thread
        thread = threading.Thread(target=self._run_loop, daemon=True)
        thread.start()

    def _run_loop(self):
        """Main Thinking Loop (Non-blocking).

        Non-blocking CPU sampling: call `cpu_percent(interval=None)` so the
        thread never stalls the daemon for a second on every tick. First call
        seeds the counter, subsequent calls return the delta since last call.
        """
        # Seed the non-blocking cpu counter so the first measurement is valid.
        try:
            psutil.cpu_percent(interval=None)
        except Exception as _e:
            logger.debug("Oracle CPU seed failed: %s", _e)

        while self.running:
            try:
                self._check_vitals()
                if self.net_scan_enabled and time.time() - self.last_net_scan > self.net_scan_interval_s:
                    self._security_sweep()
                    self.last_net_scan = time.time()
                if self.alert_queue and self.session:
                    self._speak_alert()
                time.sleep(30)  # slower loop — avoids burning battery on idle systems
            except Exception as e:
                logger.exception("Oracle Glitch: %s", e)
                time.sleep(10)

    def _check_vitals(self):
        # CPU — non-blocking variant (seeded in _run_loop).
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception as _e:
            logger.debug("Oracle CPU read failed: %s", _e)
            return
        if cpu > 90:
            self.alert_queue.append(f"boss, CPU is Critical at {cpu}%. Shall I kill background processes?")

        # Battery
        try:
            battery = psutil.sensors_battery()
            if battery and battery.percent < 20 and not battery.power_plugged:
                self.alert_queue.append(f"Power Critical: {battery.percent}%. Please connect charger.")
        except Exception as _e:
            logger.debug("Oracle battery read failed: %s", _e)

    def _security_sweep(self):
        logger.info("Oracle: Performing opt-in network discovery scan...")
        try:
            report = system_god.network_discovery()
        except Exception as e:
            logger.warning("Network scan failed: %s", e)
            return
        if "Unknown" in str(report):
            self.alert_queue.append("Security Alert: Unidentified device detected on WiFi.")

    @staticmethod
    def _sanitize_alert(alert: str) -> str:
        """Strip characters that could close the prompt envelope or inject
        additional instructions. Alerts are built from psutil/netsh output
        which could in theory include attacker-controlled strings (device
        names). We keep alerts short and printable."""
        safe = "".join(c for c in str(alert) if c.isprintable() and c not in "`{}<>\n\r")
        return safe[:240]

    def _speak_alert(self):
        """Injects voice into the Agent Session."""
        if not self.alert_queue:
            return
        alert = self._sanitize_alert(self.alert_queue.pop(0))
        logger.info("🗣️ ORACLE SPEAKING: %s", alert)
        if not self.session:
            return
        try:
            # Use the same USER_SPEAKS envelope as shell_input_sanitizer so the
            # LLM cannot mistake an alert body for a system override. We also
            # stop saying "Disregard previous context" which was a textbook
            # prompt-injection vector.
            prompt = (
                "[ORACLE ALERT — deliver as a brief spoken warning, stay in current persona]\n"
                f"<<<USER_SPEAKS>>>\n{alert}\n<<<END_USER_SPEAKS>>>"
            )
            asyncio.run_coroutine_threadsafe(
                self.session.generate_reply(instructions=prompt),
                self.session.loop,
            )
        except Exception as e:
            logger.warning("Oracle speak_alert failed: %s", e)

oracle = Oracle()
