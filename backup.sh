#!/bin/bash

# Create backup directory
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configuration files
cp .streamlit/config.toml "$BACKUP_DIR/"
cp .streamlit/secrets.toml "$BACKUP_DIR/" 2>/dev/null || true
cp requirements.txt "$BACKUP_DIR/"

# Backup logs
if [ -d "logs" ]; then
    cp -r logs "$BACKUP_DIR/"
fi

# Backup data files
if [ -d "data" ]; then
    cp -r data "$BACKUP_DIR/"
fi

# Create backup archive
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"

# Remove temporary backup directory
rm -rf "$BACKUP_DIR"

# Keep only last 7 days of backups
find backups -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR.tar.gz" 