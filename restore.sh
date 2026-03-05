#!/bin/bash
set -e

BACKUP_DIR="/Volumes/JarvisSecure/jarvis_secure/memory/backups/postgres"
DB_NAME="jarvis"
DB_USER="jarvis"

echo "[restore] Available backups:"
ls -lh "$BACKUP_DIR"/*.sql 2>/dev/null || { echo "No backups found in $BACKUP_DIR"; exit 1; }

echo ""
read -p "Enter backup filename to restore (full path): " BACKUP_FILE

if [ ! -f "$BACKUP_FILE" ]; then
    echo "File not found: $BACKUP_FILE"
    exit 1
fi

echo "[restore] Stopping Brain..."
sudo launchctl stop com.jarvis.brain 2>/dev/null || true

echo "[restore] Dropping and recreating database..."
psql postgres -c "DROP DATABASE IF EXISTS $DB_NAME;"
psql postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
psql "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "[restore] Restoring from $BACKUP_FILE..."
psql "$DB_NAME" < "$BACKUP_FILE"

echo "[restore] Restarting Brain..."
sudo launchctl start com.jarvis.brain

echo "[restore] Done. Verifying tables..."
psql "$DB_NAME" -c "\dt"
