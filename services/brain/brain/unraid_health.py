from fastapi import APIRouter
import httpx
import os

router = APIRouter()

UNRAID_URL = "http://192.168.30.10/graphql"
SECRETS_PATH = os.path.expanduser("~/jarvis/.secrets")

def _get_api_key():
    with open(SECRETS_PATH) as f:
        for line in f:
            if line.startswith("UNRAID_API_KEY="):
                return line.strip().split("=", 1)[1]
    return None

QUERY = """
{
  array {
    state
    capacity {
      kilobytes {
        total
        used
        free
      }
    }
  }
  disks {
    name
    smartStatus
    temperature
    size
  }
}
"""

@router.get("/v1/unraid/health")
async def unraid_health():
    api_key = _get_api_key()
    if not api_key:
        return {"status": "error", "message": "UNRAID_API_KEY not found in secrets"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                UNRAID_URL,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                json={"query": QUERY}
            )
            data = resp.json()
        if "errors" in data:
            return {"status": "error", "errors": data["errors"]}
        array = data["data"]["array"]
        disks = data["data"]["disks"]
        kb = array["capacity"]["kilobytes"]
        total_tb = round(int(kb["total"]) / 1024 / 1024 / 1024, 2)
        used_tb = round(int(kb["used"]) / 1024 / 1024 / 1024, 2)
        free_tb = round(int(kb["free"]) / 1024 / 1024 / 1024, 2)
        used_pct = round(used_tb / total_tb * 100, 1)
        disk_summary = []
        warn_disks = []
        for d in disks:
            entry = {
                "name": d["name"],
                "smart": d["smartStatus"],
                "temp_c": d["temperature"],
                "size_gb": round(d["size"] / 1024 / 1024 / 1024, 1) if d["size"] else 0
            }
            disk_summary.append(entry)
            if d["smartStatus"] == "FAILING":
                warn_disks.append(d["name"])
        overall = "HEALTHY"
        if warn_disks:
            overall = "CRITICAL"
        elif used_pct > 90:
            overall = "WARNING"
        return {
            "status": overall,
            "array_state": array["state"],
            "capacity": {
                "total_tb": total_tb,
                "used_tb": used_tb,
                "free_tb": free_tb,
                "used_pct": used_pct
            },
            "disks": disk_summary,
            "warn_disks": warn_disks
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
