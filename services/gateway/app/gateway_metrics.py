import psutil, time, platform, subprocess

def get_power_mw() -> int:
    try:
        out = subprocess.check_output(
            ["sudo", "powermetrics", "--samplers", "cpu_power", "-n", "1", "-i", "500"],
            stderr=subprocess.DEVNULL, timeout=6
        ).decode()
        for line in out.splitlines():
            if "Combined Power" in line:
                return int(line.split(":")[1].strip().split()[0])
    except Exception:
        return 0
    return 0

def get_metrics() -> dict:
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0,0,0)
    boot = psutil.boot_time()
    uptime_secs = time.time() - boot
    power_mw = get_power_mw()
    return {
        "cpu_pct": round(cpu, 1),
        "ram_pct": round(ram.percent, 1),
        "ram_used_gb": round(ram.used / 1e9, 2),
        "ram_total_gb": round(ram.total / 1e9, 2),
        "disk_pct": round(disk.percent, 1),
        "disk_used_gb": round(disk.used / 1e9, 2),
        "disk_total_gb": round(disk.total / 1e9, 2),
        "load_avg": f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}",
        "process_count": len(psutil.pids()),
        "uptime": f"{int(uptime_secs//86400)}d {int((uptime_secs%86400)//3600)}h",
        "uptime_secs": int(uptime_secs),
        "platform": platform.node(),
        "power_mw": power_mw,
        "power_w": round(power_mw / 1000, 2),
    }
