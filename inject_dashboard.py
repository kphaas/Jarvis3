import re

DASHBOARD_HTML = ""
with open("/Users/jarvisbrain/jarvis/jarvis_dashboard.html") as f:
    DASHBOARD_HTML = f.read()

APP_PATH = "/Users/jarvisbrain/jarvis/services/brain/brain/app.py"

with open(APP_PATH, "r") as f:
    content = f.read()

pattern = r'@app\.get\("/dashboard".*?response_class=HTMLResponse\)\ndef dashboard\(\):.*?return """.*?"""'
replacement = f'@app.get("/dashboard", response_class=HTMLResponse)\ndef dashboard():\n    return """{DASHBOARD_HTML}"""'

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

if new_content == content:
    print("ERROR: pattern not matched — check app.py dashboard section")
else:
    with open(APP_PATH, "w") as f:
        f.write(new_content)
    print("SUCCESS")
