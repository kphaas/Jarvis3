Build a morning briefing endpoint.

Context: Brain FastAPI app lives at services/brain/brain/app.py. Postgres has processed_summaries,
budget_events, and routing_decisions tables. Pattern for DB connection is in services/brain/brain/memory_service.py.

Task:
1. Read services/brain/brain/app.py to understand the route registration pattern
2. Read services/brain/brain/memory_service.py to understand the DB connection pattern
3. Create services/brain/brain/morning_briefing.py that:
   - Queries top 10 processed_summaries from last 24 hours ordered by created_at desc
   - Queries budget_events for yesterday total spend
   - Queries routing_decisions for yesterday count and most used provider
   - Returns all this as a FastAPI GET /v1/briefing endpoint with clean JSON response
   - Uses _get_conn() pattern from memory_service.py for DB access
4. Write the new file to ~/jarvis/overnight/workspace/services/brain/brain/morning_briefing.py
5. Run: python3 -m py_compile ~/jarvis/overnight/workspace/services/brain/brain/morning_briefing.py
6. Write a note in the result JSON showing exactly what lines to add to app.py to register the route
7. Write result JSON to ~/jarvis/overnight/results/02_morning_briefing.json

Result JSON must include: task name, status (pass/fail), files_changed list, one-sentence summary, any errors.
