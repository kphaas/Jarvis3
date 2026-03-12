import subprocess
import httpx
import json
import os

BRAIN = "100.64.166.22"
ENDPOINT = "100.87.223.31"
BRAIN_USER = "jarvisbrain"
ENDPOINT_USER = "jarvisendpoint"
BRAIN_API = "http://100.64.166.22:8182"
GATEWAY_API = "http://100.112.63.25:8282"

BLOCKED_PATTERNS = ["cat ~/.secrets", "cat ~/jarvis/.secrets", ".secrets", "security find-generic", "grep.*PASS", "grep.*KEY", "grep.*SECRET", "grep.*TOKEN"]

def ssh_exec(node: str, command: str) -> dict:
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in command.lower():
            return {"stdout": "", "stderr": f"BLOCKED: command contains sensitive pattern '{pattern}'", "exit_code": 1}
    user_host = f"{BRAIN_USER}@{BRAIN}" if node == "brain" else f"{ENDPOINT_USER}@{ENDPOINT}"
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", user_host, f"export PATH=/opt/homebrew/Cellar/postgresql@16/16.13/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; {command}"],
        capture_output=True, text=True, timeout=60
    )
    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "exit_code": result.returncode
    }

def http_request(method: str, url: str, body: dict = None) -> dict:
    try:
        with httpx.Client(timeout=15) as client:
            if method.upper() == "GET":
                r = client.get(url)
            elif method.upper() == "POST":
                r = client.post(url, json=body or {})
            elif method.upper() == "PATCH":
                r = client.patch(url, json=body or {})
            else:
                return {"error": f"unsupported method {method}"}
            return {"status": r.status_code, "body": r.text[:2000]}
    except Exception as e:
        return {"error": str(e)}

def write_file(node: str, path: str, content: str) -> dict:
    user_host = f"{BRAIN_USER}@{BRAIN}" if node == "brain" else f"{ENDPOINT_USER}@{ENDPOINT}"
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", user_host,
         f"cat > {path} << 'FILEEOF'\n{content}\nFILEEOF"],
        capture_output=True, text=True, timeout=30
    )
    return {"exit_code": result.returncode, "stderr": result.stderr.strip()}

def read_file(node: str, path: str) -> dict:
    return ssh_exec(node, f"cat {path}")

def restart_service(node: str, plist: str) -> dict:
    cmd = f"launchctl unload ~/Library/LaunchAgents/{plist} 2>/dev/null; sleep 2; launchctl load ~/Library/LaunchAgents/{plist}"
    return ssh_exec(node, cmd)

def post_run_result(task_name: str, status: str, summary: str, duration: int) -> dict:
    return http_request("POST", f"{BRAIN_API}/v1/overnight/runs", {
        "task_name": task_name,
        "status": status,
        "summary": summary,
        "duration_seconds": duration
    })

TOOL_DEFINITIONS = [
    {
        "name": "ssh_exec",
        "description": "Run a shell command on Brain or Endpoint node via SSH. Use for psql, file edits, git, service checks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "enum": ["brain", "endpoint"], "description": "Which node to run on"},
                "command": {"type": "string", "description": "Shell command to execute"}
            },
            "required": ["node", "command"]
        }
    },
    {
        "name": "http_request",
        "description": "Make an HTTP request to a JARVIS API endpoint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {"type": "string", "enum": ["GET", "POST", "PATCH"]},
                "url": {"type": "string", "description": "Full URL including host and port"},
                "body": {"type": "object", "description": "JSON body for POST/PATCH"}
            },
            "required": ["method", "url"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file on Brain or Endpoint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "enum": ["brain", "endpoint"]},
                "path": {"type": "string", "description": "Absolute path to file"},
                "content": {"type": "string", "description": "File content to write"}
            },
            "required": ["node", "path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file on Brain or Endpoint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "enum": ["brain", "endpoint"]},
                "path": {"type": "string"}
            },
            "required": ["node", "path"]
        }
    },
    {
        "name": "restart_service",
        "description": "Restart a LaunchAgent service on Brain or Endpoint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "enum": ["brain", "endpoint"]},
                "plist": {"type": "string", "description": "Plist filename e.g. com.jarvis.brain.plist"}
            },
            "required": ["node", "plist"]
        }
    },
    {
        "name": "task_complete",
        "description": "Signal that all tasks are complete. Call this when done.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "What was accomplished"},
                "tasks_passed": {"type": "integer"},
                "tasks_failed": {"type": "integer"}
            },
            "required": ["summary", "tasks_passed", "tasks_failed"]
        }
    }
]

def execute_tool(name: str, inputs: dict) -> str:
    try:
        if name == "ssh_exec":
            result = ssh_exec(inputs["node"], inputs["command"])
        elif name == "http_request":
            result = http_request(inputs["method"], inputs["url"], inputs.get("body"))
        elif name == "write_file":
            result = write_file(inputs["node"], inputs["path"], inputs["content"])
        elif name == "read_file":
            result = read_file(inputs["node"], inputs["path"])
        elif name == "restart_service":
            result = restart_service(inputs["node"], inputs["plist"])
        elif name == "task_complete":
            result = {"done": True, "summary": inputs["summary"]}
        else:
            result = {"error": f"unknown tool: {name}"}
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})
