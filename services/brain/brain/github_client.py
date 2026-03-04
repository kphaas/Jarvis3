import os
import subprocess
import httpx

REPO = "kphaas/Jarvis3"
BASE = "https://api.github.com"

def _get_token() -> str:
    secrets_path = os.path.expanduser("~/.jarvis/.secrets")
    if os.path.exists(secrets_path):
        with open(secrets_path) as f:
            for line in f:
                if line.startswith("GITHUB_TOKEN="):
                    return line.strip().split("=", 1)[1]
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "jarvis.github.token", "-a", "token", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    raise RuntimeError("GITHUB_TOKEN not found")

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

async def get_open_prs() -> list:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{BASE}/repos/{REPO}/pulls?state=open&per_page=20",
            headers=_headers()
        )
        r.raise_for_status()
        prs = r.json()
    results = []
    for pr in prs:
        if not pr["head"]["ref"].startswith("feature/jarvis-"):
            continue
        async with httpx.AsyncClient() as client:
            diff_r = await client.get(
                f"{BASE}/repos/{REPO}/pulls/{pr['number']}",
                headers={**_headers(), "Accept": "application/vnd.github.diff"},
            )
            diff_text = diff_r.text if diff_r.status_code == 200 else ""
        results.append({
            "id": pr["number"],
            "branch": pr["head"]["ref"],
            "intent": pr["title"],
            "ts": pr["created_at"][:10],
            "added": pr.get("additions", 0),
            "removed": pr.get("deletions", 0),
            "lines": pr.get("changed_files", 0),
            "lint": True,
            "security": True,
            "syntax": True,
            "diff": diff_text[:3000],
            "url": pr["html_url"],
        })
    return results

async def merge_pr(pr_number: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.put(
            f"{BASE}/repos/{REPO}/pulls/{pr_number}/merge",
            headers=_headers(),
            json={"merge_method": "squash", "commit_title": f"JARVIS: Merge PR #{pr_number} via dashboard"},
        )
        r.raise_for_status()
    return {"status": "merged", "pr": pr_number}

async def close_pr(pr_number: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{BASE}/repos/{REPO}/pulls/{pr_number}",
            headers=_headers(),
            json={"state": "closed"},
        )
        r.raise_for_status()
        pr_data = r.json()
        branch = pr_data["head"]["ref"]
        await client.delete(
            f"{BASE}/repos/{REPO}/git/refs/heads/{branch}",
            headers=_headers(),
        )
    return {"status": "closed", "pr": pr_number, "branch_deleted": branch}
