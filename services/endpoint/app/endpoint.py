from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psutil, time, platform, subprocess

app = FastAPI(title="Jarvis Endpoint")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://100.87.223.31:4000", "http://localhost:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/v1/metrics")
def metrics():
    cpu   = psutil.cpu_percent(interval=0.5)
    ram   = psutil.virtual_memory()
    disk  = psutil.disk_usage("/")
    boot  = psutil.boot_time()
    load  = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0,0,0)
    uptime_secs = time.time() - boot
    power_mw = get_power_mw()
    return {
        "cpu_pct":      round(cpu, 1),
        "ram_pct":      round(ram.percent, 1),
        "ram_used_gb":  round(ram.used / 1e9, 2),
        "ram_total_gb": round(ram.total / 1e9, 2),
        "disk_pct":     round(disk.percent, 1),
        "disk_used_gb": round(disk.used / 1e9, 2),
        "disk_total_gb":round(disk.total / 1e9, 2),
        "load_avg":     f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f}",
        "process_count":len(psutil.pids()),
        "uptime":       f"{int(uptime_secs//86400)}d {int((uptime_secs%86400)//3600)}h",
        "uptime_secs":  int(uptime_secs),
        "platform":     platform.node(),
        "power_mw":     power_mw,
        "power_w":      round(power_mw / 1000, 2),
    }

@app.get("/v1/services")
def services():
    def proc_running(name):
        try:
            out = subprocess.check_output(["pgrep", "-f", name], text=True)
            return len(out.strip()) > 0
        except:
            return False
    return {"node": "endpoint", "services": [
        {"name": "Dashboard (serve)", "status": "RUNNING" if proc_running("serve") else "STOPPED", "detail": "port 4000"},
        {"name": "Ollama",            "status": "RUNNING" if proc_running("ollama") else "PLANNED",  "detail": "Phase 4 — LLM"},
        {"name": "Whisper",           "status": "PLANNED", "detail": "Phase 7 — Voice STT"},
        {"name": "Avatar",            "status": "PLANNED", "detail": "Phase 7 — JARVIS face"},
        {"name": "Video Ingestion",   "status": "PLANNED", "detail": "Phase 7 — camera feed"},
    ]}
