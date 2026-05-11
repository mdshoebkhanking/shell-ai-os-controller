
import subprocess
import logging
import socket
import threading
import platform
import os
import re
import time
import requests
from shell_safe_executor import god_tier_tool as function_tool
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("SYSTEM_GOD")

# Dangerous command patterns to block
_DANGEROUS_PATTERNS = re.compile(
    r'(format\s|del\s/|rmdir\s/s|rd\s/s|shutdown|restart|rm\s-rf|mkfs|dd\sif=|:\(\)\{)',
    re.IGNORECASE
)
# Block shell metacharacters that enable command injection
_SHELL_INJECTION_PATTERN = re.compile(r'[|&;`<>]|\$\(')

# Common port-to-service mapping
_PORT_SERVICES = {
    20: "FTP-Data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 67: "DHCP", 68: "DHCP", 69: "TFTP", 80: "HTTP",
    110: "POP3", 119: "NNTP", 123: "NTP", 135: "RPC", 137: "NetBIOS",
    138: "NetBIOS", 139: "NetBIOS", 143: "IMAP", 161: "SNMP",
    194: "IRC", 443: "HTTPS", 445: "SMB", 465: "SMTPS", 514: "Syslog",
    587: "SMTP-TLS", 993: "IMAPS", 995: "POP3S", 1433: "MSSQL",
    1521: "Oracle", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 8080: "HTTP-Alt", 8443: "HTTPS-Alt",
    27017: "MongoDB",
}


class SystemGod:
    """
    Advanced Windows Control & Cyber-Sec Tools (Registry, Services, Network).
    """

    def run_cmd(self, cmd: str) -> str:
        """Run a system command with basic safety checks."""
        if _DANGEROUS_PATTERNS.search(cmd):
            logger.warning(f"🚫 Blocked dangerous command: {cmd}")
            return "❌ Command blocked by safety filter."
        if _SHELL_INJECTION_PATTERN.search(cmd):
            logger.warning(f"🚫 Blocked shell injection characters in command: {cmd}")
            return "❌ Command blocked: contains disallowed shell metacharacters."
        try:
            import shlex
            # Use cmd /c on Windows since many commands are shell builtins (net, ipconfig, etc.)
            if platform.system() == "Windows":
                # Pass the full command as a single argument to cmd /c so
                # paths/values containing spaces survive untouched. Splitting
                # on whitespace breaks `netsh wlan show profile name="My WiFi"`.
                args = ["cmd", "/c", cmd]
            else:
                args = shlex.split(cmd)
            result = subprocess.run(args, capture_output=True, text=True, timeout=30)
            return result.stdout.strip() or result.stderr.strip()
        except subprocess.TimeoutExpired:
            return "❌ Command timed out (30s limit)."
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return f"❌ Command error: {e}"

    def get_wifi_passwords(self) -> str:
        """Retrieves saved WiFi passwords."""
        try:
            out = self.run_cmd("netsh wlan show profiles")
            profiles = [line.split(":")[1].strip() for line in out.split("\n") if "All User Profile" in line]

            report = "📶 **WiFi Passwords:**\n"
            for profile in profiles:
                details = self.run_cmd(f'netsh wlan show profile name="{profile}" key=clear')
                pass_line = [line for line in details.split("\n") if "Key Content" in line]

                if pass_line:
                    password = pass_line[0].split(":")[1].strip()
                    report += f"- **{profile}**: `{password}`\n"
                else:
                    report += f"- {profile}: (Open/No Password)\n"

            if not profiles:
                 return "⚠️ No WiFi profiles found."
            return report
        except Exception as e:
            return f"❌ WiFi Error: {e}"

    def manage_service(self, service_name: str, action: str) -> str:
        """Starts/Stops a Windows service."""
        # Sanitize service name — only allow alphanumeric and underscores
        if not re.match(r'^[a-zA-Z0-9_\-]+$', service_name):
            return "❌ Invalid service name. Only alphanumeric, hyphens, and underscores allowed."
        action = action.lower()
        if action not in ["start", "stop", "restart"]:
            return "❌ Invalid action. Use start/stop/restart."

        cmd = f"net start {service_name}" if action == "start" else f"net stop {service_name}"
        if action == "restart":
            self.run_cmd(f"net stop {service_name}")
            cmd = f"net start {service_name}"

        out = self.run_cmd(cmd)
        return f"⚙️ Service [{service_name}] Action [{action}]:\n{out}"

    def registry_tweak(self, path: str, key: str, value: str, type_: str = "REG_SZ") -> str:
        """Modifies Windows Registry with safety validation."""
        # Block dangerous registry paths
        dangerous_paths = ["HKLM\\SYSTEM\\CurrentControlSet\\Control", "HKLM\\SAM", "HKLM\\SECURITY"]
        for dp in dangerous_paths:
            if dp.lower() in path.lower():
                return f"❌ Registry path '{path}' is protected. Operation blocked."
        if type_ not in ["REG_SZ", "REG_DWORD", "REG_EXPAND_SZ", "REG_MULTI_SZ"]:
            return f"❌ Invalid registry type: {type_}"
        cmd = f'reg add "{path}" /v "{key}" /t {type_} /d "{value}" /f'
        out = self.run_cmd(cmd)
        return f"🔧 Registry Tweak:\n{out}"

    # --- HACKER TOOLS ---

    def get_public_ip(self):
        try:
            return requests.get("https://api.ipify.org", timeout=5).text
        except Exception:
            return "Unavailable"

    def deep_system_recon(self) -> str:
        """Gather deep system info including CPU count, RAM, GPU, disk, and uptime."""
        info = {
            "OS": platform.system(),
            "Release": platform.release(),
            "Version": platform.version(),
            "Machine": platform.machine(),
            "Processor": platform.processor(),
            "CPU Cores (Logical)": os.cpu_count() or "Unknown",
            "Hostname": socket.gethostname(),
            "Local IP": socket.gethostbyname(socket.gethostname()),
            "Public IP": self.get_public_ip(),
            "Current User": os.getlogin(),
        }

        # Total RAM
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_ram_gb = mem.ullTotalPhys / (1024 ** 3)
            avail_ram_gb = mem.ullAvailPhys / (1024 ** 3)
            info["Total RAM"] = f"{total_ram_gb:.2f} GB"
            info["Available RAM"] = f"{avail_ram_gb:.2f} GB"
            info["RAM Usage"] = f"{mem.dwMemoryLoad}%"
        except Exception:
            info["Total RAM"] = "Unknown"

        # GPU Info (try wmi first, fallback to wmic)
        try:
            import wmi
            w = wmi.WMI()
            gpus = w.Win32_VideoController()
            gpu_list = [g.Name for g in gpus if g.Name]
            info["GPU"] = ", ".join(gpu_list) if gpu_list else "Unknown"
        except Exception:
            try:
                gpu_out = self.run_cmd("wmic path win32_videocontroller get name")
                gpu_lines = [line.strip() for line in gpu_out.split("\n") if line.strip() and line.strip().lower() != "name"]
                info["GPU"] = ", ".join(gpu_lines) if gpu_lines else "Unknown"
            except Exception:
                info["GPU"] = "Unknown"

        # Disk Info
        try:
            import shutil
            for drive_letter in "CDEFGH":
                drive = f"{drive_letter}:\\"
                if os.path.exists(drive):
                    usage = shutil.disk_usage(drive)
                    total_gb = usage.total / (1024 ** 3)
                    free_gb = usage.free / (1024 ** 3)
                    used_pct = ((usage.total - usage.free) / usage.total) * 100
                    info[f"Disk {drive_letter}:"] = f"Total: {total_gb:.1f} GB | Free: {free_gb:.1f} GB | Used: {used_pct:.1f}%"
        except Exception:
            info["Disk"] = "Unknown"

        # System Uptime
        try:
            uptime_out = self.run_cmd("wmic os get lastbootuptime")
            lines = [l.strip() for l in uptime_out.split("\n") if l.strip() and l.strip().lower() != "lastbootuptime"]
            if lines:
                boot_str = lines[0].split(".")[0]  # e.g. 20260315083000
                from datetime import datetime
                boot_time = datetime.strptime(boot_str, "%Y%m%d%H%M%S")
                uptime_delta = datetime.now() - boot_time
                days = uptime_delta.days
                hours, remainder = divmod(uptime_delta.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                info["Uptime"] = f"{days}d {hours}h {minutes}m"
        except Exception:
            info["Uptime"] = "Unknown"

        report = "🕵️ **DEEP RECON REPORT** 🕵️\n"
        for k, v in info.items():
            report += f"- **{k}**: `{v}`\n"
        return report

    def scan_ports(self, target_ip: str, ports: list = None) -> str:
        """Port Scanner with service name mapping and timing."""
        start_time = time.time()

        if not ports:
            ports = [21, 22, 23, 25, 53, 80, 110, 135, 139, 143, 443, 445,
                     993, 995, 1433, 3306, 3389, 5432, 5900, 8080, 8443]

        open_ports = []

        def check_port(ip, port):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            if result == 0:
                open_ports.append(port)
            sock.close()

        with ThreadPoolExecutor(max_workers=50) as executor:
            for port in ports:
                executor.submit(check_port, target_ip, port)

        elapsed = time.time() - start_time

        if open_ports:
            report = f"🔓 **OPEN PORTS on {target_ip}:**\n"
            for p in sorted(open_ports):
                service = _PORT_SERVICES.get(p, "Unknown")
                report += f"  - Port `{p}` ({service}) ✅ OPEN\n"
            report += f"\n⏱️ Scan completed in `{elapsed:.2f}s` | Ports scanned: `{len(ports)}`"
            return report
        else:
            return f"🔒 No open ports found on {target_ip}.\n⏱️ Scan completed in `{elapsed:.2f}s` | Ports scanned: `{len(ports)}`"

    def network_discovery(self) -> str:
        """Ping sweep local subnet with timeout protection."""
        local_ip = socket.gethostbyname(socket.gethostname())
        base_ip = ".".join(local_ip.split(".")[:-1])

        live_hosts = []

        def ping(ip):
            try:
                if platform.system() == "Windows":
                    args = ["ping", "-n", "1", "-w", "200", ip]
                else:
                    args = ["ping", "-c", "1", "-W", "1", ip]
                response = subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                if response.returncode == 0:
                    live_hosts.append(ip)
            except (subprocess.TimeoutExpired, OSError):
                pass  # Ping timed out or failed; skip this host

        report = f"🌐 **NETWORK SCAN (Subnet {base_ip}.x)**\nScanning...\n"

        targets = [f"{base_ip}.{i}" for i in range(1, 255)]

        with ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(ping, targets)

        report += "\n".join([f"✅ ONLINE: {host}" for host in sorted(live_hosts, key=lambda x: int(x.split('.')[-1]))])
        if not live_hosts:
            report += "No hosts found."
        return report

    def god_tier_optimizer(self) -> str:
        """
        System cleanup protocol.
        Cleans Temp, Prefetch, and Flushes DNS.
        """
        start_time = time.time()
        report = "🧰 **SYSTEM CLEANUP STARTED**\n\n"

        try:
            # 1. Flush DNS
            dns_res = self.run_cmd("ipconfig /flushdns")
            report += f"🌐 **DNS Flush:** {dns_res.splitlines()[-1] if dns_res else 'Success'}\n"

            # 2. Clear TEMP (User + System)
            temp_dirs = [os.environ.get('TEMP', ''), os.environ.get('TMP', ''), r"C:\Windows\Temp"]
            freed_mb = 0

            for t_dir in temp_dirs:
                if not t_dir or not os.path.exists(t_dir):
                    continue
                dir_count = 0
                for f in os.listdir(t_dir):
                    f_path = os.path.join(t_dir, f)
                    try:
                        if os.path.isfile(f_path):
                            size = os.path.getsize(f_path)
                            os.remove(f_path)
                            freed_mb += size
                            dir_count += 1
                        elif os.path.isdir(f_path):
                            import shutil
                            # Calculate roughly before delete
                            freed_mb += sum(os.path.getsize(os.path.join(dirpath, filename))
                                            for dirpath, _, filenames in os.walk(f_path)
                                            for filename in filenames)
                            shutil.rmtree(f_path, ignore_errors=True)
                            dir_count += 1
                    except Exception as e:
                        logger.debug(f"Could not remove {f_path}: {e}")  # File likely in use
                report += f"🗑️ **{t_dir}**: `{dir_count}` files/folders cleaned\n"

            report += f"💾 **Total Temp Junk Cleared:** ~{freed_mb / (1024*1024):.2f} MB\n"

            # 3. Clean Prefetch folder
            prefetch_dir = r"C:\Windows\Prefetch"
            prefetch_count = 0
            prefetch_size = 0
            if os.path.exists(prefetch_dir):
                for f in os.listdir(prefetch_dir):
                    f_path = os.path.join(prefetch_dir, f)
                    try:
                        if os.path.isfile(f_path):
                            prefetch_size += os.path.getsize(f_path)
                            os.remove(f_path)
                            prefetch_count += 1
                    except Exception as e:
                        logger.debug(f"Could not remove prefetch file {f_path}: {e}")
                report += f"📁 **Prefetch Cleanup:** `{prefetch_count}` files removed (~{prefetch_size / (1024*1024):.2f} MB)\n"
            else:
                report += "📁 **Prefetch:** Directory not found (skipped)\n"

            # 4. WSReset (Windows Store Cache - Async)
            try:
                subprocess.Popen(["wsreset.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                report += "🛒 **Windows Store Cache:** Resetting in background.\n"
            except FileNotFoundError:
                report += "🛒 **Windows Store Cache:** wsreset.exe not found (skipped).\n"

            elapsed = time.time() - start_time
            report += f"\n⏱️ **Total Optimization Time:** `{elapsed:.2f}s`"
            report += "\n✅ **Cleanup completed. Review the details above for what changed.**"
            return report

        except Exception as e:
            return f"❌ Optimization Error: {e}"

    # --- STARTUP MANAGER ---

    def manage_startup(self, action: str = "list", program_name: str = "") -> str:
        """List, disable, or enable startup programs via registry."""
        reg_path = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
        disabled_path = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run_Disabled"

        action = action.lower().strip()
        if action not in ("list", "disable", "enable"):
            return "❌ Invalid action. Use: list, disable, enable."

        if action == "list":
            out = self.run_cmd(f'reg query "{reg_path}"')
            report = "🚀 **STARTUP PROGRAMS (Enabled):**\n"
            if out and "ERROR" not in out.upper():
                lines = [l.strip() for l in out.split("\n") if "REG_" in l]
                if lines:
                    for line in lines:
                        parts = line.split("    ")
                        parts = [p.strip() for p in parts if p.strip()]
                        if len(parts) >= 3:
                            name = parts[0]
                            value = parts[2]
                            report += f"  ✅ **{name}** -> `{value}`\n"
                else:
                    report += "  (No startup programs found)\n"
            else:
                report += "  (No startup programs found)\n"

            # Also show disabled ones
            out_disabled = self.run_cmd(f'reg query "{disabled_path}"')
            if out_disabled and "ERROR" not in out_disabled.upper():
                lines = [l.strip() for l in out_disabled.split("\n") if "REG_" in l]
                if lines:
                    report += "\n🚫 **STARTUP PROGRAMS (Disabled):**\n"
                    for line in lines:
                        parts = line.split("    ")
                        parts = [p.strip() for p in parts if p.strip()]
                        if len(parts) >= 3:
                            name = parts[0]
                            value = parts[2]
                            report += f"  ❌ **{name}** -> `{value}`\n"
            return report

        if not program_name:
            return "❌ program_name required for enable/disable action. Pehle 'list' karke naam dekh lo."

        # Sanitize program_name
        if not re.match(r'^[a-zA-Z0-9_\-\. ]+$', program_name):
            return "❌ Invalid program name. Sirf alphanumeric, spaces, dots, hyphens allowed."

        if action == "disable":
            # Read value from Run, save to Run_Disabled, delete from Run
            out = self.run_cmd(f'reg query "{reg_path}" /v "{program_name}"')
            if "ERROR" in out.upper() or "REG_" not in out:
                return f"❌ '{program_name}' startup mein nahi mila. Pehle 'list' karke check karo."
            # Extract value
            for line in out.split("\n"):
                if "REG_" in line:
                    parts = line.strip().split("    ")
                    parts = [p.strip() for p in parts if p.strip()]
                    if len(parts) >= 3:
                        reg_type = parts[1]
                        reg_value = parts[2]
                        # Save to disabled path
                        self.run_cmd(f'reg add "{disabled_path}" /v "{program_name}" /t {reg_type} /d "{reg_value}" /f')
                        # Delete from enabled
                        self.run_cmd(f'reg delete "{reg_path}" /v "{program_name}" /f')
                        return f"🚫 **{program_name}** startup se disable kar diya gaya hai! Restart ke baad effect hoga."
            return f"❌ '{program_name}' ka value parse nahi ho paya."

        if action == "enable":
            # Read value from Run_Disabled, save to Run, delete from Run_Disabled
            out = self.run_cmd(f'reg query "{disabled_path}" /v "{program_name}"')
            if "ERROR" in out.upper() or "REG_" not in out:
                return f"❌ '{program_name}' disabled list mein nahi mila. Pehle 'list' karke check karo."
            for line in out.split("\n"):
                if "REG_" in line:
                    parts = line.strip().split("    ")
                    parts = [p.strip() for p in parts if p.strip()]
                    if len(parts) >= 3:
                        reg_type = parts[1]
                        reg_value = parts[2]
                        # Save to enabled path
                        self.run_cmd(f'reg add "{reg_path}" /v "{program_name}" /t {reg_type} /d "{reg_value}" /f')
                        # Delete from disabled
                        self.run_cmd(f'reg delete "{disabled_path}" /v "{program_name}" /f')
                        return f"✅ **{program_name}** startup mein wapas enable kar diya! Restart ke baad chalega."
            return f"❌ '{program_name}' ka value parse nahi ho paya."

        return "❌ Unknown error."

    # --- INSTALLED PROGRAMS ---

    def list_installed_programs(self, search: str = "") -> str:
        """List installed programs from registry with optional search filter."""
        reg_paths = [
            r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        ]

        programs = []
        for reg_path in reg_paths:
            out = self.run_cmd(f'reg query "{reg_path}" /s')
            if not out or "ERROR" in out.upper():
                continue

            current = {}
            for line in out.split("\n"):
                line = line.strip()
                if line.startswith("HKLM\\") or line.startswith("HKEY_"):
                    if current.get("DisplayName"):
                        programs.append(current)
                    current = {}
                elif "REG_" in line:
                    parts = line.split("    ")
                    parts = [p.strip() for p in parts if p.strip()]
                    if len(parts) >= 3:
                        key = parts[0]
                        val = parts[2]
                        if key == "DisplayName":
                            current["DisplayName"] = val
                        elif key == "DisplayVersion":
                            current["DisplayVersion"] = val
                        elif key == "Publisher":
                            current["Publisher"] = val
                        elif key == "InstallDate":
                            current["InstallDate"] = val
            # Last entry
            if current.get("DisplayName"):
                programs.append(current)

        # Deduplicate by name
        seen = set()
        unique_programs = []
        for p in programs:
            name = p.get("DisplayName", "")
            if name not in seen:
                seen.add(name)
                unique_programs.append(p)

        # Apply search filter
        if search:
            search_lower = search.lower()
            unique_programs = [p for p in unique_programs if search_lower in p.get("DisplayName", "").lower()]

        # Sort alphabetically
        unique_programs.sort(key=lambda x: x.get("DisplayName", "").lower())

        if not unique_programs:
            if search:
                return f"❌ Koi program nahi mila '{search}' search ke liye."
            return "❌ Installed programs ki list nahi mil payi."

        report = f"📦 **INSTALLED PROGRAMS** ({len(unique_programs)} found"
        if search:
            report += f", search: '{search}'"
        report += "):\n\n"

        for p in unique_programs:
            name = p.get("DisplayName", "N/A")
            version = p.get("DisplayVersion", "-")
            publisher = p.get("Publisher", "-")
            install_date = p.get("InstallDate", "-")
            report += f"  📌 **{name}**\n"
            report += f"     Version: `{version}` | Publisher: `{publisher}` | Installed: `{install_date}`\n"

        return report

    # --- FIREWALL STATUS ---

    def get_firewall_status(self) -> str:
        """Shows Windows Firewall status for all profiles."""
        out = self.run_cmd("netsh advfirewall show allprofiles")
        if not out or "ERROR" in out.upper():
            return "❌ Firewall status nahi mil paya. Admin privileges required ho sakte hain."

        report = "🛡️ **WINDOWS FIREWALL STATUS** 🛡️\n\n"

        current_profile = ""
        for line in out.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Detect profile headers
            if "Domain Profile" in line:
                current_profile = "🏢 Domain Profile"
                report += f"\n**{current_profile}:**\n"
            elif "Private Profile" in line:
                current_profile = "🏠 Private Profile"
                report += f"\n**{current_profile}:**\n"
            elif "Public Profile" in line:
                current_profile = "🌐 Public Profile"
                report += f"\n**{current_profile}:**\n"
            elif "State" in line and current_profile:
                state = line.split()[-1] if line.split() else "Unknown"
                emoji = "✅" if state.upper() == "ON" else "❌"
                report += f"  - Firewall State: {emoji} `{state}`\n"
            elif "Firewall Policy" in line and current_profile:
                policy = line.split("Firewall Policy")[-1].strip() if "Firewall Policy" in line else "Unknown"
                report += f"  - Firewall Policy: `{policy}`\n"
            elif "InboundConnections" in line or "Inbound" in line and "connection" in line.lower():
                val = line.split()[-1] if line.split() else "Unknown"
                report += f"  - Inbound: `{val}`\n"
            elif "OutboundConnections" in line or "Outbound" in line and "connection" in line.lower():
                val = line.split()[-1] if line.split() else "Unknown"
                report += f"  - Outbound: `{val}`\n"

        if report.strip() == "🛡️ **WINDOWS FIREWALL STATUS** 🛡️":
            report += "\n(Raw output):\n" + out[:1000]

        return report


system_god = SystemGod()

@function_tool
async def get_wifi_leaks_tool() -> str:
    """
    🕵️ EXPOSE WIFI PASSWORDS.
    Retrieves all saved WiFi passwords on this PC.
    """
    return system_god.get_wifi_passwords()

@function_tool
async def manage_windows_service_tool(service_name: str, action: str) -> str:
    """
    ⚙️ MANAGE WINDOWS SERVICES.
    Args:
        service_name: Name of service (e.g., "wuauserv", "Spooler").
        action: "start", "stop", or "restart".
    """
    return system_god.manage_service(service_name, action)

@function_tool
async def registry_hack_tool(root_path: str, key_name: str, value_data: str) -> str:
    """
    🔧 EDIT WINDOWS REGISTRY (Advanced).
    Use with caution. Can change system settings.
    """
    return system_god.registry_tweak(root_path, key_name, value_data)

@function_tool
async def system_recon_tool() -> str:
    """
    🕵️ SYSTEM RECON (WhoAmI) - ENHANCED.
    Gets Public IP, Local IP, OS Version, Hostname, Hardware Info,
    CPU cores, Total/Available RAM, GPU info, Disk usage, and System Uptime.
    """
    return system_god.deep_system_recon()

@function_tool
async def port_scan_tool(target_ip: str, ports: str = "") -> str:
    """
    🔓 PORT SCANNER - ENHANCED.
    Checks for open ports on a target IP with service name detection.
    Args:
        target_ip: IP address to scan (e.g., "192.168.1.1").
        ports: Comma-separated port numbers to scan (e.g., "80,443,8080"). Leave empty for default common ports.
    """
    port_list = None
    if ports and ports.strip():
        try:
            port_list = [int(p.strip()) for p in ports.split(",") if p.strip().isdigit()]
            if not port_list:
                return "❌ Invalid ports format. Use comma-separated numbers like '80,443,8080'."
        except ValueError:
            return "❌ Invalid ports format. Use comma-separated numbers like '80,443,8080'."
    return system_god.scan_ports(target_ip, port_list)

@function_tool
async def net_scan_tool() -> str:
    """
    🌐 NETWORK DISCOVERY (Ping Sweep).
    Finds other devices connected to the same WiFi/Network.
    """
    return system_god.network_discovery()

@function_tool
async def god_tier_optimizer_tool() -> str:
    """
    🚀 LEVEL 10000 PC OPTIMIZER - ENHANCED.
    Cleans Temp/Junk files, Prefetch folder, flushes DNS, resets Windows Cache.
    Shows per-directory cleanup count and total optimization time. Use when PC is slow!
    """
    return system_god.god_tier_optimizer()

# ==================== NEW TOOLS ====================

@function_tool
async def startup_manager_tool(action: str = "list", program_name: str = "") -> str:
    """
    🚀 STARTUP MANAGER - List/Disable/Enable startup programs.
    Controls which programs run at Windows startup via registry.
    Args:
        action: "list" to see all startup programs, "disable" to remove from startup, "enable" to re-add.
        program_name: Name of the program (required for disable/enable). Use 'list' first to see names.
    """
    return system_god.manage_startup(action, program_name)

@function_tool
async def installed_programs_tool(search: str = "") -> str:
    """
    📦 INSTALLED PROGRAMS VIEWER.
    Lists all installed programs with name, version, publisher, and install date.
    Args:
        search: Optional search filter to find specific programs (e.g., "chrome", "python").
    """
    return system_god.list_installed_programs(search)

@function_tool
async def firewall_status_tool() -> str:
    """
    🛡️ WINDOWS FIREWALL STATUS.
    Shows firewall state for Domain, Private, and Public profiles.
    Displays whether firewall is ON/OFF, inbound/outbound policies.
    """
    return system_god.get_firewall_status()
