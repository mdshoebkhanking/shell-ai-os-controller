#!/usr/bin/env python3
import os
import psutil
import logging
import subprocess
from typing import Dict, Any
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_diag")

@function_tool
async def scan_system_health() -> str:
    """
    Scans the entire system (CPU, GPU, RAM, Disk) to diagnose performance issues.
    Use this if the user asks "why is my PC slow?" or "system status kya hai?".
    """
    try:
        logger.info("🛡️ Initiating System Diagnostic Scan...")
        
        # 1. CPU Info
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq().current if psutil.cpu_freq() else "N/A"
        
        # 2. RAM Info
        ram = psutil.virtual_memory()
        ram_total = round(ram.total / (1024**3), 2)
        ram_used = round(ram.used / (1024**3), 2)
        ram_percent = ram.percent
        
        # 3. Disk Info
        disk = psutil.disk_usage('/')
        disk_total = round(disk.total / (1024**3), 2)
        disk_free = round(disk.free / (1024**3), 2)
        disk_percent = disk.percent
        
        # 4. GPU Info (Windows Fallback)
        gpu_info = "N/A"
        try:
            if os.name == 'nt':
                output = subprocess.check_output(["wmic", "path", "win32_VideoController", "get", "name"]).decode()
                gpu_info = output.split('\n')[1].strip()
        except Exception:
            pass  # GPU detection is optional

        # 5. Top Processes (Heaviest)
        procs = []
        for proc in psutil.process_iter(['name', 'cpu_percent']):
            try:
                procs.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        top_procs = sorted(procs, key=lambda item: item.get("cpu_percent") or 0.0, reverse=True)[:3]
        proc_str = ", ".join(
            f"{item.get('name') or 'Unknown'} ({item.get('cpu_percent') or 0.0}%)" for item in top_procs
        )

        # 6. Temperature Info
        temp_str = "N/A"
        try:
            if hasattr(psutil, 'sensors_temperatures') and psutil.sensors_temperatures():
                temps = psutil.sensors_temperatures()
                temp_parts = []
                for chip, entries in temps.items():
                    for entry in entries:
                        temp_parts.append(f"{chip}/{entry.label or 'core'}: {entry.current}°C")
                temp_str = ", ".join(temp_parts) if temp_parts else "N/A"
            elif os.name == 'nt':
                # WMI fallback for Windows
                wmi_out = subprocess.check_output(
                    ["powershell", "-Command",
                     "Get-CimInstance MSAcpi_ThermalZoneTemperature -Namespace root/wmi 2>$null | Select-Object -ExpandProperty CurrentTemperature"],
                    stderr=subprocess.DEVNULL, timeout=5
                ).decode().strip()
                if wmi_out:
                    # Value is in tenths of Kelvin
                    for line in wmi_out.splitlines():
                        line = line.strip()
                        if line.isdigit():
                            celsius = round((int(line) / 10) - 273.15, 1)
                            temp_str = f"{celsius}°C"
                            break
        except Exception:
            temp_str = "N/A (sensor data unavailable)"

        # 7. Network Status
        net_status = "Disconnected"
        ip_address = "N/A"
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            net_status = "Connected"
        except Exception:
            net_status = "Disconnected"

        # 8. Boot Time & Uptime
        import datetime
        boot_ts = psutil.boot_time()
        boot_time = datetime.datetime.fromtimestamp(boot_ts).strftime("%Y-%m-%d %H:%M:%S")
        uptime_secs = int((datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_ts)).total_seconds())
        uptime_hrs = uptime_secs // 3600
        uptime_mins = (uptime_secs % 3600) // 60
        uptime_str = f"{uptime_hrs}h {uptime_mins}m"

        # 9. Swap / Page File Usage
        swap = psutil.swap_memory()
        swap_total = round(swap.total / (1024**3), 2)
        swap_used = round(swap.used / (1024**3), 2)
        swap_percent = swap.percent

        # 10. Conclusion logic for Shell
        conclusion = "Sir, system normal lag raha hai."
        if cpu_usage > 80: conclusion = "Sir, CPU utilization bohot high hai, kuch heavy tasks chal rahe hain."
        elif ram_percent > 85: conclusion = "Sir, RAM lagbhag full ho gayi hai, isliye PC slow mehsus ho raha hai."
        elif disk_percent > 90: conclusion = "Sir, aapki C: drive full hai, thodi space khali karni chahiye."

        report = f"""
--- SYSTEM DIAGNOSTIC REPORT ---
🖥️ GPU: {gpu_info}
⚙️ CPU: {cpu_usage}% (Current: {cpu_freq}MHz, Cores: {cpu_count})
🌡️ Temperature: {temp_str}
🧠 RAM: {ram_used}GB / {ram_total}GB ({ram_percent}%)
📄 Swap/PageFile: {swap_used}GB / {swap_total}GB ({swap_percent}%)
💾 Disk: {disk_free}GB khali / {disk_total}GB ({disk_percent}%)
🌐 Network: {net_status} (IP: {ip_address})
⏱️ Boot Time: {boot_time} | Uptime: {uptime_str}
🔥 Top Tasks: {proc_str}
-------------------------------
💡 Conclusion: {conclusion}
"""
        logger.info("✅ Diagnostic Scan Complete.")
        return report

    except Exception as e:
        logger.error(f"Diagnostic Scan failed: {e}")
        return f"❌ System scan fail ho gaya: {str(e)}"

@function_tool
async def check_network_health_tool() -> str:
    """
    Tests internet connectivity, DNS resolution, latency aur speed estimate.
    Use this if user asks "internet slow hai?", "network check karo", "ping test karo".
    """
    try:
        import socket
        import time
        import urllib.request

        logger.info("🌐 Network Health Check shuru ho raha hai...")

        results = []
        fast_probe = os.environ.get("SHELL_FAST_TOOL_PROBE") == "1"
        ping_count = "1" if fast_probe else "4"
        ping_timeout = 3 if fast_probe else 15

        # 1. Ping test (ICMP via subprocess) to 8.8.8.8
        ping_status = "❌ Failed"
        latency = "N/A"
        try:
            if os.name == 'nt':
                ping_out = subprocess.check_output(
                    ["ping", "-n", ping_count, "8.8.8.8"],
                    stderr=subprocess.DEVNULL, timeout=ping_timeout
                ).decode()
                # Parse average latency from Windows ping output
                for line in ping_out.splitlines():
                    if "Average" in line or "average" in line:
                        parts = line.split("=")
                        if len(parts) >= 2:
                            latency = parts[-1].strip()
                ping_status = "✅ Reachable"
            else:
                ping_out = subprocess.check_output(
                    ["ping", "-c", ping_count, "8.8.8.8"],
                    stderr=subprocess.DEVNULL, timeout=ping_timeout
                ).decode()
                for line in ping_out.splitlines():
                    if "avg" in line:
                        latency = line.split("/")[4] + "ms"
                ping_status = "✅ Reachable"
        except Exception as e:
            ping_status = f"❌ Ping fail: {e}"

        results.append(f"📡 Google DNS (8.8.8.8): {ping_status} | Latency: {latency}")

        # 2. DNS Resolution
        dns_status = "❌ Failed"
        try:
            start = time.time()
            ip = socket.gethostbyname("google.com")
            dns_time = round((time.time() - start) * 1000, 2)
            dns_status = f"✅ google.com -> {ip} ({dns_time}ms)"
        except Exception as e:
            dns_status = f"❌ DNS resolution fail: {e}"

        results.append(f"🔍 DNS Resolution: {dns_status}")

        # 3. Speed Test
        speed_str = ""
        try:
            if fast_probe:
                raise RuntimeError("skipped in fast probe mode")
            # Try speedtest-cli first
            speed_out = subprocess.check_output(
                ["speedtest-cli", "--simple"],
                stderr=subprocess.DEVNULL, timeout=60
            ).decode().strip()
            speed_str = speed_out
        except Exception:
            # Fallback: simple download test
            try:
                test_url = "http://speedtest.tele2.net/1MB.zip"
                start = time.time()
                with urllib.request.urlopen(test_url, timeout=3 if fast_probe else 10) as response:
                    response.read(256 * 1024 if fast_probe else 1024 * 1024)
                elapsed = time.time() - start
                sample_mb = 0.25 if fast_probe else 1
                speed_mbps = round((sample_mb * 8) / elapsed, 2)
                label = "256KB" if fast_probe else "1MB"
                speed_str = f"Download: ~{speed_mbps} Mbit/s (estimated from {label} test file)"
            except Exception as e2:
                speed_str = f"Speed test unavailable: {e2}"

        results.append(f"🚀 Speed: {speed_str}")

        # 4. Network interfaces summary
        net_io = psutil.net_io_counters()
        sent_mb = round(net_io.bytes_sent / (1024**2), 2)
        recv_mb = round(net_io.bytes_recv / (1024**2), 2)
        results.append(f"📊 Total Sent: {sent_mb}MB | Received: {recv_mb}MB (since boot)")

        report = "\n--- NETWORK HEALTH REPORT ---\n"
        report += "\n".join(results)
        report += "\n-----------------------------\n"

        logger.info("✅ Network Health Check complete.")
        return report

    except Exception as e:
        logger.error(f"Network health check failed: {e}")
        return f"❌ Network health check fail ho gaya: {str(e)}"


@function_tool
async def check_disk_health_tool() -> str:
    """
    Disk ki detailed health check karta hai - SMART status, I/O rates, large files, fragmentation.
    Use this if user asks "disk health kaise hai?", "disk slow hai", "kaunsi files space le rahi hain?".
    """
    try:
        logger.info("💾 Disk Health Check shuru ho raha hai...")

        results = []

        # 1. SMART Status (Windows via wmic)
        smart_status = "N/A"
        try:
            if os.name == 'nt':
                smart_out = subprocess.check_output(
                    ["wmic", "diskdrive", "get", "status,model,size"],
                    stderr=subprocess.DEVNULL, timeout=10
                ).decode().strip()
                lines = [l.strip() for l in smart_out.splitlines() if l.strip()]
                smart_status = "\n  ".join(lines)
            else:
                smart_status = "SMART check sirf Windows pe supported hai via wmic"
        except Exception as e:
            smart_status = f"SMART check fail: {e}"

        results.append(f"🔧 SMART Status:\n  {smart_status}")

        # 2. Disk I/O Rates
        try:
            io1 = psutil.disk_io_counters()
            import time
            time.sleep(1)
            io2 = psutil.disk_io_counters()
            read_speed = round((io2.read_bytes - io1.read_bytes) / (1024**2), 2)
            write_speed = round((io2.write_bytes - io1.write_bytes) / (1024**2), 2)
            results.append(f"📖 Disk I/O: Read: {read_speed} MB/s | Write: {write_speed} MB/s")
        except Exception as e:
            results.append(f"📖 Disk I/O: measurement fail: {e}")

        # 3. Partition info
        partitions = psutil.disk_partitions()
        for part in partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = round(usage.total / (1024**3), 2)
                used_gb = round(usage.used / (1024**3), 2)
                free_gb = round(usage.free / (1024**3), 2)
                results.append(
                    f"💿 {part.device} ({part.fstype}): {used_gb}GB / {total_gb}GB used | {free_gb}GB free ({usage.percent}%)"
                )
            except (PermissionError, OSError):
                pass

        # 4. Large Files (Top 10 files > 100MB in user home)
        large_files = []
        home_dir = os.path.expanduser("~")
        try:
            for root, dirs, files in os.walk(home_dir):
                # Skip hidden/system directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('AppData', '__pycache__', 'node_modules')]
                for f in files:
                    try:
                        fpath = os.path.join(root, f)
                        fsize = os.path.getsize(fpath)
                        if fsize > 100 * 1024 * 1024:  # > 100MB
                            large_files.append((fpath, fsize))
                    except (OSError, PermissionError):
                        pass
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        large_files.sort(key=lambda x: x[1], reverse=True)
        top_large = large_files[:10]
        if top_large:
            results.append("📦 Top Large Files (>100MB in user home):")
            for fp, fs in top_large:
                size_mb = round(fs / (1024**2), 2)
                results.append(f"  📄 {fp} — {size_mb} MB")
        else:
            results.append("📦 Koi file >100MB nahi mili user home mein.")

        # 5. Fragmentation Status (Windows only)
        frag_status = "N/A"
        try:
            if os.name == 'nt':
                frag_out = subprocess.check_output(
                    ["powershell", "-Command",
                     "Optimize-Volume -DriveLetter C -Analyze -Verbose 2>&1 | Out-String"],
                    stderr=subprocess.DEVNULL, timeout=30
                ).decode().strip()
                frag_status = frag_out if frag_out else "Analysis returned no output"
        except Exception as e:
            frag_status = f"Fragmentation check fail: {e}"

        results.append(f"🧩 Fragmentation (C:): {frag_status}")

        report = "\n--- DISK HEALTH REPORT ---\n"
        report += "\n".join(results)
        report += "\n--------------------------\n"

        logger.info("✅ Disk Health Check complete.")
        return report

    except Exception as e:
        logger.error(f"Disk health check failed: {e}")
        return f"❌ Disk health check fail ho gaya: {str(e)}"


@function_tool
async def list_resource_hogs_tool(top_n: int = 10) -> str:
    """
    Top N processes jo sabse zyada CPU aur RAM kha rahe hain unki list dikhata hai.
    Use this if user asks "kaun sa process zyada CPU use kar raha?", "RAM kaun kha raha?", "resource hogs dikhao".
    """
    try:
        logger.info(f"🔥 Top {top_n} Resource Hogs dhoondh raha hai...")

        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'status']):
            try:
                info = proc.info
                ram_mb = round(info['memory_info'].rss / (1024**2), 2) if info['memory_info'] else 0
                procs.append({
                    'pid': info['pid'],
                    'name': info['name'],
                    'cpu_percent': info['cpu_percent'] or 0,
                    'ram_mb': ram_mb,
                    'status': info['status']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Sort by CPU first, then RAM
        procs_by_cpu = sorted(procs, key=lambda x: x['cpu_percent'], reverse=True)[:top_n]
        procs_by_ram = sorted(procs, key=lambda x: x['ram_mb'], reverse=True)[:top_n]

        report = f"\n--- TOP {top_n} RESOURCE HOGS ---\n"

        report += "\n🔥 BY CPU USAGE:\n"
        report += f"{'PID':<8} {'Name':<30} {'CPU%':<8} {'RAM(MB)':<12} {'Status'}\n"
        report += "-" * 75 + "\n"
        for p in procs_by_cpu:
            report += f"{p['pid']:<8} {p['name']:<30} {p['cpu_percent']:<8} {p['ram_mb']:<12} {p['status']}\n"

        report += "\n🧠 BY RAM USAGE:\n"
        report += f"{'PID':<8} {'Name':<30} {'CPU%':<8} {'RAM(MB)':<12} {'Status'}\n"
        report += "-" * 75 + "\n"
        for p in procs_by_ram:
            report += f"{p['pid']:<8} {p['name']:<30} {p['cpu_percent']:<8} {p['ram_mb']:<12} {p['status']}\n"

        report += "-------------------------------\n"
        report += f"💡 Total processes running: {len(procs)}\n"

        logger.info("✅ Resource Hog scan complete.")
        return report

    except Exception as e:
        logger.error(f"Resource hog scan failed: {e}")
        return f"❌ Resource hog scan fail ho gaya: {str(e)}"


@function_tool
async def get_event_log_errors_tool(count: int = 10) -> str:
    """
    Recent Windows Event Log errors dikhata hai - system crashes, service failures, etc.
    Use this if user asks "koi system error aaya?", "event log check karo", "Windows errors dikhao".
    """
    try:
        logger.info(f"📋 Last {count} Event Log Errors fetch kar raha hai...")

        if os.name != 'nt':
            return "❌ Yeh tool sirf Windows pe kaam karta hai. Linux pe journalctl use karo."

        errors = []

        # Try wevtutil first (faster)
        try:
            cmd = f'wevtutil qe System /q:"*[System[Level=2]]" /c:{count} /f:text /rd:true'
            output = subprocess.check_output(
                cmd, shell=True, stderr=subprocess.DEVNULL, timeout=15
            ).decode(errors='replace').strip()

            if output:
                # Parse wevtutil text output
                current_event = {}
                for line in output.splitlines():
                    line = line.strip()
                    if line.startswith("Event["):
                        if current_event:
                            errors.append(current_event)
                        current_event = {}
                    elif ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip()
                        if key == "Source":
                            current_event['source'] = val
                        elif key == "Date":
                            current_event['date'] = val
                        elif key == "Description":
                            current_event['message'] = val
                if current_event:
                    errors.append(current_event)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        # Fallback to PowerShell if wevtutil didn't work well
        if not errors:
            try:
                ps_cmd = (
                    f"Get-EventLog -LogName System -EntryType Error -Newest {count} "
                    f"| Format-List Source, TimeGenerated, Message"
                )
                ps_out = subprocess.check_output(
                    ["powershell", "-Command", ps_cmd],
                    stderr=subprocess.DEVNULL, timeout=30
                ).decode(errors='replace').strip()

                if ps_out:
                    current_event = {}
                    for line in ps_out.splitlines():
                        line = line.strip()
                        if not line:
                            if current_event:
                                errors.append(current_event)
                                current_event = {}
                            continue
                        if ":" in line:
                            key, _, val = line.partition(":")
                            key = key.strip()
                            val = val.strip()
                            if key == "Source":
                                current_event['source'] = val
                            elif key == "TimeGenerated":
                                current_event['date'] = val
                            elif key == "Message":
                                current_event['message'] = val[:200]  # Truncate long messages
                    if current_event:
                        errors.append(current_event)
            except Exception as e2:
                return f"❌ Event log fetch fail ho gaya (dono methods): {e2}"

        if not errors:
            return "✅ Koi recent system error nahi mila Event Log mein. Sab theek chal raha hai!"

        report = f"\n--- LAST {count} SYSTEM ERRORS (Event Log) ---\n"
        for i, evt in enumerate(errors[:count], 1):
            src = evt.get('source', 'Unknown')
            date = evt.get('date', 'Unknown')
            msg = evt.get('message', 'No description')
            report += f"\n🔴 Error #{i}:\n"
            report += f"   Source: {src}\n"
            report += f"   Time:   {date}\n"
            report += f"   Message: {msg}\n"

        report += "\n---------------------------------------------\n"
        report += f"💡 Total {len(errors[:count])} errors shown. Agar zyada chahiye toh count badha do.\n"

        logger.info("✅ Event Log fetch complete.")
        return report

    except Exception as e:
        logger.error(f"Event log fetch failed: {e}")
        return f"❌ Event log check fail ho gaya: {str(e)}"


@function_tool
async def diagnose_voice_hardware_tool() -> str:
    """
    Checks voice hardware input/output devices and presence of required TTS/STT models.
    Use this if the user asks "why is voice not working?", "voice diagnostics run karo",
    or if the UI needs to report voice readiness.
    """
    import json
    import os
    from pathlib import Path
    
    microphone_present = False
    microphone_details = "No input devices detected"
    speaker_present = False
    speaker_details = "No output devices detected"
    
    # Check audio devices
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devs = [d for d in devices if d.get("max_input_channels", 0) > 0]
        output_devs = [d for d in devices if d.get("max_output_channels", 0) > 0]
        
        if input_devs:
            microphone_present = True
            microphone_details = f"Found input device: {input_devs[0]['name']}"
        if output_devs:
            speaker_present = True
            speaker_details = f"Found output device: {output_devs[0]['name']}"
    except Exception as exc:
        microphone_details = f"Failed to query audio devices: {exc}"
        speaker_details = f"Failed to query audio devices: {exc}"

    # Check Kokoro TTS model
    kokoro_present = False
    kokoro_path = None
    try:
        from shell_offline_tts import _candidate_model_dirs, _find_kokoro_model
        paths = _candidate_model_dirs("kokoro")
        model_path, voices_path, model_dir = _find_kokoro_model(paths)
        if model_path and voices_path:
            kokoro_present = True
            kokoro_path = str(model_path)
    except Exception:
        pass

    # Check Sherpa-ONNX STT models
    sherpa_present = False
    sherpa_missing = []
    try:
        from shell_local_stt import LocalSTTConfig
        cfg = LocalSTTConfig.from_environment()
        if not cfg.tokens:
            sherpa_missing.append("tokens.txt")
        if not cfg.encoder:
            sherpa_missing.append("encoder-epoch-99-avg-1.int8.onnx")
        if not cfg.decoder:
            sherpa_missing.append("decoder-epoch-99-avg-1.onnx")
        if not cfg.joiner:
            sherpa_missing.append("joiner-epoch-99-avg-1.int8.onnx")
        
        sherpa_present = len(sherpa_missing) == 0
    except Exception as exc:
        sherpa_missing.append(f"Config load error: {exc}")

    ok = bool(microphone_present and speaker_present and kokoro_present and sherpa_present)

    result = {
        "ok": ok,
        "microphone": {
            "present": microphone_present,
            "details": microphone_details
        },
        "speaker": {
            "present": speaker_present,
            "details": speaker_details
        },
        "kokoro_model": {
            "present": kokoro_present,
            "path": kokoro_path
        },
        "sherpa_models": {
            "present": sherpa_present,
            "missing_files": sherpa_missing
        }
    }

    return json.dumps(result, ensure_ascii=True)


__all__ = [
    'scan_system_health',
    'check_network_health_tool',
    'check_disk_health_tool',
    'list_resource_hogs_tool',
    'get_event_log_errors_tool',
    'diagnose_voice_hardware_tool'
]
