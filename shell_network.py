#!/usr/bin/env python3
import os
import socket
import logging
import subprocess
import re
import asyncio
from shell_safe_executor import god_tier_tool as function_tool

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger("shell_network")

@function_tool
async def get_network_info() -> str:
    """
    Retrieves detailed network information:
    - Public IP & Location
    - Local IP & Gateway
    - WiFi SSID
    - Active connections count
    - Network speed test (if speedtest-cli available)
    """
    try:
        logger.info("Fetching Network Info...")

        # 1. Local Info
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        # 2. Public IP & Location
        try:
            result = subprocess.run(
                ["curl", "-s", "ipinfo.io"],
                capture_output=True, text=True, timeout=10
            )
            import json
            data = json.loads(result.stdout)
            public_ip = data.get('ip', 'Unknown')
            city = data.get('city', 'Unknown')
            region = data.get('region', '')
            country = data.get('country', '')
            org = data.get('org', 'Unknown')
            location = f"{city}, {region}, {country}" if region else f"{city}, {country}"
        except Exception:
            public_ip = "Unknown"
            location = "Unknown"
            org = "Unknown"

        # 3. WiFi SSID
        ssid = "N/A"
        signal = ""
        if os.name == 'nt':
            try:
                out = subprocess.check_output(
                    ["netsh", "wlan", "show", "interfaces"],
                    timeout=10
                ).decode(errors='ignore')
                for line in out.split('\n'):
                    if "SSID" in line and "BSSID" not in line:
                        ssid = line.split(":")[1].strip()
                    if "Signal" in line:
                        signal = line.split(":")[1].strip()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # 4. Active connections
        active_connections = 0
        if PSUTIL_AVAILABLE:
            try:
                connections = psutil.net_connections(kind='inet')
                active_connections = len([c for c in connections if c.status == 'ESTABLISHED'])
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # 5. Network I/O
        net_io = ""
        if PSUTIL_AVAILABLE:
            try:
                net = psutil.net_io_counters()
                sent = net.bytes_sent / (1024**2)
                recv = net.bytes_recv / (1024**2)
                net_io = f"   - Upload: {sent:.0f} MB | Download: {recv:.0f} MB (since boot)"
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        # 6. Speed test
        speed_report = "   ⏭️ Speed test skipped (run 'pip install speedtest-cli' for speed test)"
        try:
            subprocess.run(["speedtest-cli", "--version"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            res = subprocess.run(
                ["speedtest-cli", "--simple"],
                capture_output=True, text=True, timeout=30
            )
            if res.returncode == 0:
                speed_report = f"   🚀 Speed Test:\n   {res.stdout.strip().replace(chr(10), chr(10) + '   ')}"
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        signal_str = f" ({signal})" if signal else ""

        report = f"""🌐 NETWORK DIAGNOSTIC REPORT

📍 Identity:
   - Hostname: {hostname}
   - Local IP: {local_ip}
   - Public IP: {public_ip}
   - Location: {location}
   - ISP: {org}

📶 Connection:
   - WiFi: {ssid}{signal_str}
   - Status: Connected ✅
   - Active Connections: {active_connections}
{f'{net_io}' if net_io else ''}

{speed_report}"""
        return report

    except Exception as e:
        return f"❌ Network diagnostic failed: {e}"


@function_tool
async def ping_host_tool(host: str, count: int = 4) -> str:
    """
    Pings a host to check connectivity and latency.
    Args:
        host: Hostname or IP to ping (e.g., 'google.com', '8.8.8.8').
        count: Number of pings (1-10, default 4).
    """
    # Validate host — only allow hostnames and IPs
    if not re.match(r'^[a-zA-Z0-9.\-:]+$', host):
        return "❌ Invalid host format."

    count = max(1, min(10, count))

    try:
        if os.name == 'nt':
            cmd = ["ping", "-n", str(count), host]
        else:
            cmd = ["ping", "-c", str(count), host]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        output = stdout.decode(errors='ignore')

        if "could not find host" in output.lower() or "request timed out" in output.lower():
            return f"❌ {host} unreachable or not found."

        # Extract summary
        lines = output.strip().split('\n')
        summary_lines = [l for l in lines if any(k in l.lower() for k in ['average', 'packets', 'loss', 'minimum'])]
        summary = "\n".join(summary_lines[-3:]) if summary_lines else output[-500:]

        return f"🏓 Ping {host} ({count} packets):\n```\n{summary}\n```"
    except asyncio.TimeoutError:
        return f"❌ Ping to {host} timed out."
    except Exception as e:
        return f"❌ Ping error: {e}"


@function_tool
async def dns_lookup_tool(domain: str) -> str:
    """
    Performs DNS lookup for a domain.
    Args:
        domain: Domain name (e.g., 'google.com', 'github.com').
    """
    if not re.match(r'^[a-zA-Z0-9.\-]+$', domain):
        return "❌ Invalid domain format."

    try:
        # A record — offload the blocking getaddrinfo to a thread executor
        # so the async event loop doesn't stall on slow DNS servers.
        loop = asyncio.get_event_loop()
        ips = await loop.run_in_executor(None, socket.getaddrinfo, domain, None, socket.AF_INET)
        ipv4_set = set()
        for addr in ips:
            ipv4_set.add(addr[4][0])

        # Try nslookup for more info
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True, text=True, timeout=10
        )
        nslookup_output = result.stdout[:800] if result.stdout else ""

        ipv4_list = "\n".join(f"   - {ip}" for ip in ipv4_set)

        return (
            f"🔍 DNS Lookup: {domain}\n\n"
            f"IPv4 Addresses:\n{ipv4_list}\n\n"
            f"Details:\n```\n{nslookup_output}\n```"
        )
    except socket.gaierror:
        return f"❌ Domain '{domain}' not found."
    except Exception as e:
        return f"❌ DNS lookup error: {e}"


@function_tool
async def check_port_tool(host: str, port: int) -> str:
    """
    Checks if a specific port is open on a host.
    Args:
        host: Hostname or IP (e.g., 'google.com', 'localhost').
        port: Port number (e.g., 80, 443, 22, 3389).
    """
    if not re.match(r'^[a-zA-Z0-9.\-:]+$', host):
        return "❌ Invalid host."
    if port < 1 or port > 65535:
        return "❌ Port must be 1-65535."

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()

        common_ports = {
            21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
            80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 445: "SMB",
            993: "IMAPS", 995: "POP3S", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 5900: "VNC", 8080: "HTTP-Alt", 8443: "HTTPS-Alt"
        }
        service = common_ports.get(port, "Unknown")

        if result == 0:
            return f"✅ Port {port} ({service}) is OPEN on {host}"
        else:
            return f"❌ Port {port} ({service}) is CLOSED on {host}"
    except socket.timeout:
        return f"⏱️ Port {port} on {host} — connection timed out (filtered/blocked)"
    except Exception as e:
        return f"❌ Port check error: {e}"


@function_tool
async def traceroute_tool(host: str) -> str:
    """
    Traces the network route to a host (shows all hops).
    Args:
        host: Hostname or IP (e.g., 'google.com').
    """
    if not re.match(r'^[a-zA-Z0-9.\-]+$', host):
        return "❌ Invalid host."

    try:
        if os.name == 'nt':
            cmd = ["tracert", "-d", "-h", "15", host]
        else:
            cmd = ["traceroute", "-m", "15", host]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
        output = stdout.decode(errors='ignore')

        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"

        return f"🔀 Traceroute to {host}:\n```\n{output}\n```"
    except asyncio.TimeoutError:
        return f"⏱️ Traceroute to {host} timed out (60s)."
    except Exception as e:
        return f"❌ Traceroute error: {e}"


__all__ = [
    'get_network_info', 'ping_host_tool', 'dns_lookup_tool',
    'check_port_tool', 'traceroute_tool'
]
