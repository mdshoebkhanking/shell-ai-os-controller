import asyncio
import subprocess
import platform
import os
from shell_safe_executor import god_tier_tool as function_tool
import logging

# Try importing psutil for advanced features
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger("shell_system_pro")

async def run_powershell(script):
    process = await asyncio.create_subprocess_shell(
        f"powershell -Command \"{script}\"",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode().strip()

@function_tool
async def system_power_tool(action: str) -> str:
    """
    Controls system power state.
    Args:
        action: 'lock' (Only Lock is allowed).
    """
    try:
        # STRICT SAFETY: User disabled Shutdown, Restart, Sleep.
        if action.lower() in ["shutdown", "restart", "sleep"]:
            return f"🛡️ ACCESS DENIED: boss ne mana kiya hai. ({action} is disabled for safety)"

        elif action == "lock":
            cmd = "rundll32.exe user32.dll,LockWorkStation"
            msg = "🔒 System Locked."
        else:
            return "❌ Unknown action. Use: lock."

        subprocess.Popen(cmd.split())
        return msg
    except Exception as e:
        return f"❌ Power Error: {e}"

@function_tool
async def get_system_specs_tool() -> str:
    """Gets detailed system specifications (CPU, RAM, OS, Disk, Network, Uptime)."""
    try:
        info = []
        info.append(f"💻 System: {platform.system()} {platform.release()} ({platform.version()})")
        info.append(f"🧠 Processor: {platform.processor()}")
        info.append(f"🏗️ Architecture: {platform.machine()}")
        info.append(f"🖥️ Hostname: {platform.node()}")

        if PSUTIL_AVAILABLE:
            # RAM
            mem = psutil.virtual_memory()
            total_gb = round(mem.total / (1024**3), 2)
            used_gb = round(mem.used / (1024**3), 2)
            available_gb = round(mem.available / (1024**3), 2)
            info.append(f"💾 RAM: {used_gb}GB used / {total_gb}GB total ({mem.percent}%) | Available: {available_gb}GB")

            # CPU
            cpu_count = psutil.cpu_count(logical=True)
            cpu_physical = psutil.cpu_count(logical=False)
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                info.append(f"⚡ CPU: {cpu_physical} cores / {cpu_count} threads @ {cpu_freq.current:.0f}MHz")
            info.append(f"📊 CPU Usage: {psutil.cpu_percent(interval=0.5)}%")

            # Disk
            partitions = psutil.disk_partitions()
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    total = usage.total / (1024**3)
                    free = usage.free / (1024**3)
                    info.append(f"💿 {p.device}: {usage.percent}% used ({total:.0f}GB total, {free:.0f}GB free)")
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)

            # Battery
            battery = psutil.sensors_battery()
            if battery:
                plugged = "🔌 Plugged In" if battery.power_plugged else "🔋 On Battery"
                secs = battery.secsleft
                time_left = ""
                if secs > 0 and secs != psutil.POWER_TIME_UNLIMITED:
                    hours = secs // 3600
                    mins = (secs % 3600) // 60
                    time_left = f" | ~{hours}h {mins}m remaining"
                info.append(f"🔋 Battery: {battery.percent}% ({plugged}{time_left})")

            # Uptime
            boot_time = psutil.boot_time()
            import time
            uptime_seconds = int(time.time() - boot_time)
            hours = uptime_seconds // 3600
            mins = (uptime_seconds % 3600) // 60
            info.append(f"⏱️ Uptime: {hours}h {mins}m")

            # Network
            net = psutil.net_io_counters()
            sent_gb = net.bytes_sent / (1024**3)
            recv_gb = net.bytes_recv / (1024**3)
            info.append(f"🌐 Network: ↑{sent_gb:.2f}GB sent | ↓{recv_gb:.2f}GB received")
        else:
            info.append("⚠️ psutil not installed. Install it for detailed stats.")

        return "\n".join(info)
    except Exception as e:
        return f"❌ Error getting specs: {e}"

@function_tool
async def get_running_processes_tool(filter_name: str = None) -> str:
    """
    Lists top running processes by memory usage.
    Args:
        filter_name: Optional name to filter (e.g., 'chrome').
    """
    if not PSUTIL_AVAILABLE:
        return "❌ 'psutil' library missing. Cannot list processes."

    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
            try:
                if filter_name and filter_name.lower() not in p.info['name'].lower():
                    continue
                procs.append(p.info)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # Sort by memory usage
        procs.sort(key=lambda x: x['memory_percent'] or 0, reverse=True)

        # Limit output
        top_procs = procs[:20]
        output = [f"--- TOP {len(top_procs)} PROCESSES (by RAM) ---"]
        for p in top_procs:
            mem = f"{p['memory_percent']:.1f}%" if p['memory_percent'] else "?"
            cpu = f"{p['cpu_percent']:.0f}%" if p.get('cpu_percent') else "?"
            output.append(f"🆔 {p['pid']} | {p['name']} | RAM: {mem} | CPU: {cpu}")

        return "\n".join(output)
    except Exception as e:
        return f"❌ Error listing processes: {e}"

@function_tool
async def kill_process_tool(process_name: str) -> str:
    """
    Terminates a process by name.
    Args:
        process_name: Name of process to kill (e.g., 'notepad.exe').
    """
    if not PSUTIL_AVAILABLE:
        return "❌ 'psutil' library missing."

    try:
        killed_count = 0
        access_denied_count = 0

        for p in psutil.process_iter(['pid', 'name']):
            try:
                if process_name.lower() in p.info['name'].lower():
                    try:
                        p.kill()
                        killed_count += 1
                        logger.info(f"Killed process: {p.info['name']} (PID: {p.pid})")
                    except psutil.AccessDenied:
                        access_denied_count += 1

            except (psutil.NoSuchProcess):
                continue

        if killed_count > 0:
            msg = f"✅ Killed {killed_count} instances of '{process_name}'."
            if access_denied_count > 0:
                msg += f" (⚠️ Failed {access_denied_count} due to permission)"
            return msg

        if access_denied_count > 0:
            return f"❌ Found '{process_name}' but Access Denied. Run Shell as Administrator."

        return f"⚠️ No running process found matching '{process_name}'."
    except Exception as e:
        return f"❌ Error killing process: {e}"

@function_tool
async def get_battery_status_tool() -> str:
    """Gets battery info with time remaining estimate."""
    if PSUTIL_AVAILABLE:
        try:
            battery = psutil.sensors_battery()
            if not battery: return "❌ No battery detected (Desktop?)."
            status = "Charging ⚡" if battery.power_plugged else "Discharging 🔋"
            time_left = ""
            if battery.secsleft > 0 and battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                hours = battery.secsleft // 3600
                mins = (battery.secsleft % 3600) // 60
                time_left = f" | ~{hours}h {mins}m remaining"
            return f"🔋 Battery: {battery.percent}% | Status: {status}{time_left}"
        except Exception as e:
            return f"❌ Battery Error: {e}"
    else:
        try:
            script = "Get-WmiObject Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus"
            output = await run_powershell(script)
            return f"🔋 (Legacy) {output.strip()}"
        except Exception:
             return "❌ Battery info unavailable."

@function_tool
async def set_brightness_tool(level: int) -> str:
    """Sets screen brightness (0-100)."""
    try:
        level = max(0, min(100, level))
        script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
        await run_powershell(script)
        return f"🔆 Brightness set to {level}%."
    except Exception as e:
        return f"❌ Brightness failed (Desktop monitors might not support software control): {e}"

@function_tool
async def get_wifi_password_tool(profile_name: str = "") -> str:
    """
    Gets saved WiFi password. Shows current network password if no profile specified.
    Args:
        profile_name: WiFi network name. Leave empty for current network.
    """
    try:
        if not profile_name:
            # Get current WiFi name
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, text=True, timeout=10
            )
            import re
            match = re.search(r'SSID\s+:\s+(.+)', result.stdout)
            if match:
                profile_name = match.group(1).strip()
            else:
                return "⚠️ WiFi se connected nahi ho ya WiFi adapter nahi mila."

        result = subprocess.run(
            ["netsh", "wlan", "show", "profile", profile_name, "key=clear"],
            capture_output=True, text=True, timeout=10
        )

        if "is not found" in result.stdout or result.returncode != 0:
            return f"❌ WiFi profile '{profile_name}' nahi mila."

        import re
        password_match = re.search(r'Key Content\s+:\s+(.+)', result.stdout)
        password = password_match.group(1).strip() if password_match else "Not found"

        auth_match = re.search(r'Authentication\s+:\s+(.+)', result.stdout)
        auth = auth_match.group(1).strip() if auth_match else "Unknown"

        return (
            f"🔑 WiFi Password:\n"
            f"  📶 Network: {profile_name}\n"
            f"  🔐 Password: {password}\n"
            f"  🛡️ Security: {auth}"
        )
    except Exception as e:
        return f"❌ WiFi password error: {e}"

@function_tool
async def list_saved_wifi_tool() -> str:
    """Lists all saved WiFi network profiles."""
    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True, text=True, timeout=10
        )
        import re
        profiles = re.findall(r'All User Profile\s+:\s+(.+)', result.stdout)
        if not profiles:
            return "⚠️ No saved WiFi profiles found."

        output = f"📶 Saved WiFi Networks ({len(profiles)}):\n\n"
        for i, name in enumerate(profiles, 1):
            output += f"  {i}. {name.strip()}\n"
        output += "\n💡 'wifi password <name>' se password dekho"
        return output
    except Exception as e:
        return f"❌ Error: {e}"

@function_tool
async def get_installed_apps_tool(search: str = "") -> str:
    """
    Lists installed applications on PC.
    Args:
        search: Optional search filter (e.g., 'chrome', 'python'). Shows all if empty.
    """
    try:
        script = (
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
            "| Select-Object DisplayName, DisplayVersion, Publisher, InstallDate "
            "| Where-Object { $_.DisplayName -ne $null } "
            "| Sort-Object DisplayName "
            "| Format-Table -AutoSize -Wrap"
        )
        output = await run_powershell(script)

        if search:
            lines = output.split("\n")
            header = lines[:2] if len(lines) > 2 else []
            filtered = [l for l in lines[2:] if search.lower() in l.lower()]
            if not filtered:
                return f"⚠️ No installed app matching '{search}'."
            output = "\n".join(header + filtered[:25])

        # Trim if too long
        if len(output) > 3000:
            output = output[:3000] + "\n... (truncated)"

        return f"📦 Installed Apps:\n```\n{output}\n```"
    except Exception as e:
        return f"❌ Error: {e}"

@function_tool
async def get_startup_apps_tool() -> str:
    """Lists programs that run at Windows startup."""
    try:
        script = (
            "Get-CimInstance Win32_StartupCommand "
            "| Select-Object Name, Command, Location "
            "| Format-Table -AutoSize -Wrap"
        )
        output = await run_powershell(script)

        if not output.strip():
            # Fallback to registry
            script2 = (
                "Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' "
                "| Format-List"
            )
            output = await run_powershell(script2)

        return f"🚀 Startup Programs:\n```\n{output}\n```"
    except Exception as e:
        return f"❌ Error: {e}"

@function_tool
async def get_system_uptime_tool() -> str:
    """Gets system uptime and boot time."""
    if PSUTIL_AVAILABLE:
        try:
            import time
            from datetime import datetime
            boot = psutil.boot_time()
            boot_dt = datetime.fromtimestamp(boot)
            uptime_secs = int(time.time() - boot)
            days = uptime_secs // 86400
            hours = (uptime_secs % 86400) // 3600
            mins = (uptime_secs % 3600) // 60

            return (
                f"⏱️ System Uptime:\n"
                f"  Running: {days}d {hours}h {mins}m\n"
                f"  Boot Time: {boot_dt.strftime('%Y-%m-%d %I:%M %p')}"
            )
        except Exception as e:
            return f"❌ Uptime error: {e}"
    else:
        try:
            output = await run_powershell("(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime")
            return f"⏱️ Uptime: {output}"
        except Exception:
            return "❌ Uptime unavailable."

@function_tool
async def disk_cleanup_tool() -> str:
    """Cleans temporary files to free up disk space (safe cleanup only)."""
    try:
        import shutil
        cleaned = 0
        errors = []

        # Temp folders to clean
        temp_dirs = [
            os.environ.get("TEMP", ""),
            os.environ.get("TMP", ""),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp"),
        ]

        for temp_dir in temp_dirs:
            if not temp_dir or not os.path.exists(temp_dir):
                continue
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        os.remove(item_path)
                        cleaned += size
                    elif os.path.isdir(item_path):
                        size = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, fnames in os.walk(item_path)
                            for f in fnames
                        )
                        shutil.rmtree(item_path, ignore_errors=True)
                        cleaned += size
                except (PermissionError, OSError):
                    pass  # Skip files in use

        cleaned_mb = cleaned / (1024 * 1024)
        return f"🧹 Disk Cleanup Done!\n  Freed: {cleaned_mb:.1f} MB from temp files"
    except Exception as e:
        return f"❌ Cleanup error: {e}"
