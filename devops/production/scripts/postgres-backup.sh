#!/bin/sh
# PostgreSQL Backup Script for Cadence Production
# Runs daily via cron to backup database

set -e

# Configuration from environment
BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-cadence}"
POSTGRES_USER="${POSTGRES_USER:-cadence}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/postgres_${POSTGRES_DB}_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/postgres_backup.log"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Main backup function
backup_postgres() {
    log "Starting PostgreSQL backup for database: ${POSTGRES_DB}"

    # Set password for pg_dump
    export PGPASSWORD="$POSTGRES_PASSWORD"

    # Perform backup with compression
    if pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --verbose \
        --format=plain \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists | gzip > "$BACKUP_FILE"; then

        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log "Backup completed successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"

        # Verify backup integrity
        if gzip -t "$BACKUP_FILE" 2>&1 | tee -a "$LOG_FILE"; then
            log "Backup integrity verified"
        else
            log "ERROR: Backup integrity check failed"
            return 1
        fi
    else
        log "ERROR: Backup failed"
        return 1
    fi

    # Unset password
    unset PGPASSWORD
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days"

    find "$BACKUP_DIR" -name "postgres_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

    REMAINING_COUNT=$(find "$BACKUP_DIR" -name "postgres_*.sql.gz" -type f | wc -l)
    log "Cleanup completed. Remaining backups: ${REMAINING_COUNT}"
}

# Send notification (optional, implement your notification method)
send_notification() {
    STATUS=$1
    MESSAGE=$2

    # Example: Send to webhook, email, or monitoring service
    # curl -X POST "https://your-webhook-url" \
    #     -H "Content-Type: application/json" \
    #     -d "{\"status\": \"$STATUS\", \"message\": \"$MESSAGE\", \"service\": \"postgres-backup\"}"

    log "Notification: ${STATUS} - ${MESSAGE}"
}

# Main execution
main() {
    log "======================================"
    log "PostgreSQL Backup Script Started"
    log "======================================"

    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"

    # Perform backup
    if backup_postgres; then
        cleanup_old_backups
        send_notification "SUCCESS" "PostgreSQL backup completed successfully"
        log "Backup process completed successfully"
        exit 0
    else
        send_notification "ERROR" "PostgreSQL backup failed"
        log "Backup process failed"
        exit 1
    fi
}

# Run main function
main
