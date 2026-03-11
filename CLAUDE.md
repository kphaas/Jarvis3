# JARVIS — Claude Code Context

## Architecture
- Brain (Mac Studio brain.jarvis.internal): orchestration, Postgres 16, routing, FastAPI :8182
- Gateway (this machine): cloud proxy, Claude API, Perplexity, Claude Code runs here
- Endpoint (Mac Mini endpoint.jarvis.internal): dashboard :4000, voice :4001, avatar :4002

## Repo structure
- services/brain/brain/ — Brain FastAPI app, venv at services/brain/.venv, Python 3.14
- services/gateway/ — Gateway proxy service
- services/voice/ — Voice UI
- services/ingest/ — Feed ingest service :8185
- services/auth/ — Auth service :8183
- dashboard/ — React dashboard

## Critical rules — never violate these
- NEVER commit to main — write files to ~/jarvis/overnight/workspace/ only
- NEVER run git commit or git push — human reviews all changes
- ALWAYS run python -m py_compile on every .py file you create or edit
- ALWAYS delete __pycache__ after editing any .py file
- Brain venv is services/brain/.venv — never use root .venv
- Postgres is Homebrew postgresql@16, jarvisbrain user, jarvis database
- Model string is claude-haiku-4-5-20251001
- Secrets live in ~/jarvis/.secrets (chmod 600), never use keyring library
- router.py route() returns only {target, reason} — never calls APIs directly

## Output instructions
- Write all new or modified files to ~/jarvis/overnight/workspace/ mirroring repo structure
- Example: a fix to services/ingest/feed_fetcher.py goes to ~/jarvis/overnight/workspace/services/ingest/feed_fetcher.py
- After writing each file, run py_compile on it
- Write a JSON result file to ~/jarvis/overnight/results/<task_name>.json with keys: task, status, files_changed, summary, errors

## Postgres connection (Brain)
- Host: brain.jarvis.internal, port: 5432, user: jarvis, database: jarvis
- Pattern: use psycopg2, read password from ~/jarvis/.secrets POSTGRES_PASSWORD key
