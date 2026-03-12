#!/bin/zsh
DATESTAMP=$(date +%Y%m%d)
BACKUP_DIR=~/jarvis/backups/postgres/base/$DATESTAMP
/opt/homebrew/Cellar/postgresql@16/16.13/bin/pg_basebackup -h localhost -U jarvis -D $BACKUP_DIR -Ft -z -P
rsync -a -e "ssh -i ~/.ssh/unraid_backup" $BACKUP_DIR root@192.168.30.10:/mnt/user/Documents/Jarvis/postgres-wal-backup/base/
rm -rf $BACKUP_DIR
