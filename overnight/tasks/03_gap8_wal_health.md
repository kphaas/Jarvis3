# Task 03 — WAL Archive Health Check

## Objective
Verify the Postgres WAL archive pipeline is healthy end-to-end. Report only, no changes.

## Checks to Perform

1. Confirm archive_mode and archive_timeout are set correctly in postgresql.conf
   - Expected: archive_mode = on, archive_timeout = 300

2. Count WAL segments currently on Unraid
   - Path: /mnt/user/Documents/Jarvis/postgres-wal-backup/wal/
   - Report count and size of files
   - Report timestamp of most recent file

3. Check the most recent file age
   - If newest WAL file is older than 15 minutes, flag as WARNING
   - If newer than 15 minutes, flag as HEALTHY

4. Confirm base backup exists on Unraid
   - Path: /mnt/user/Documents/Jarvis/postgres-wal-backup/base/
   - Report folder names and sizes present

5. Check Brain local backup log for errors
   - Path: ~/jarvis/backups/postgres/backup.log
   - Report last 10 lines if file exists

6. Check Postgres is running and accepting connections
   - Run: psql postgresql://jarvis:jarvisdb@localhost:5432/jarvis -c "SELECT now();"

## SSH Access for Unraid
- Host: 192.168.30.10
- User: root
- Key: ~/.ssh/unraid_backup

## Report Format
Return a structured summary with:
- Overall status: HEALTHY / WARNING / CRITICAL
- Each check result with PASS / FAIL / WARNING
- Any recommended actions if issues found
