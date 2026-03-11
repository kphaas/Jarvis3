import psutil
import time
import platform


def get_metrics() -> dict:
    """Return Gateway system metrics without blocking calls."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    load = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)
    boot = psutil.boot_time()
    uptime_secs = time.time() - boot
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
        "uptime_secs": int(uptime_secs),
        "platform": platform.node(),
    }
