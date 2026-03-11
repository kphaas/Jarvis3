Fix the Atlanta news feed.

Context: services/ingest/feed_fetcher.py has dead feed sources for the atlanta_news category.
WSB-TV and AJC URLs timeout. Reddit RSS already works for other categories via Gateway proxy.

Task:
1. Read services/ingest/feed_fetcher.py to understand the current feed source structure
2. Find the atlanta_news feed sources
3. Replace broken URLs with: https://www.reddit.com/r/atlanta/.rss
4. Follow exactly the same pattern used for other Reddit RSS sources in the file
5. Write the fixed file to ~/jarvis/overnight/workspace/services/ingest/feed_fetcher.py
6. Run: python3 -m py_compile ~/jarvis/overnight/workspace/services/ingest/feed_fetcher.py
7. Write result JSON to ~/jarvis/overnight/results/01_atlanta_feed.json

Result JSON must include: task name, status (pass/fail), files_changed list, one-sentence summary, any errors.
