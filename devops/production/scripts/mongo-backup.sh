#!/bin/sh
# MongoDB Backup Script for Cadence Production
# Runs daily via cron to backup all Cadence databases

set -e

# Configuration from environment
BACKUP_DIR="${BACKUP_DIR:-/backups}"
MONGO_HOST="${MONGO_HOST:-mongo}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_ROOT_USER="${MONGO_ROOT_USER:-cadence}"
MONGO_ROOT_PASSWORD="${MONGO_ROOT_PASSWORD:?MONGO_ROOT_PASSWORD is required}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Generate timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_PATH="${BACKUP_DIR}/mongo_${TIMESTAMP}"
ARCHIVE_FILE="${BACKUP_PATH}.tar.gz"
LOG_FILE="${BACKUP_DIR}/mongo_backup.log"

# Log function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Main backup function
backup_mongo() {
    log "Starting MongoDB backup for all Cadence databases"

    # Build connection string
    MONGO_URI="mongodb://${MONGO_ROOT_USER}:${MONGO_ROOT_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}"

    # Perform backup with mongodump
    if mongodump \
        --uri="$MONGO_URI" \
        --out="$BACKUP_PATH" \
        --gzip \
        --verbose 2>&1 | tee -a "$LOG_FILE"; then

        log "MongoDB dump completed successfully: ${BACKUP_PATH}"

        # Create compressed archive
        if tar -czf "$ARCHIVE_FILE" -C "$BACKUP_DIR" "$(basename "$BACKUP_PATH")"; then
            ARCHIVE_SIZE=$(du -h "$ARCHIVE_FILE" | cut -f1)
            log "Archive created successfully: ${ARCHIVE_FILE} (${ARCHIVE_SIZE})"

            # Remove uncompressed dump directory
            rm -rf "$BACKUP_PATH"
            log "Temporary dump directory removed"

            # Verify archive integrity
            if tar -tzf "$ARCHIVE_FILE" > /dev/null 2>&1; then
                log "Archive integrity verified"
            else
                log "ERROR: Archive integrity check failed"
                return 1
            fi
        else
            log "ERROR: Failed to create archive"
            return 1
        fi
    else
        log "ERROR: MongoDB dump failed"
        return 1
    fi
}

# Backup specific database (optional)
backup_specific_database() {
    DATABASE_NAME=$1
    log "Starting MongoDB backup for database: ${DATABASE_NAME}"

    MONGO_URI="mongodb://${MONGO_ROOT_USER}:${MONGO_ROOT_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}"
    DB_BACKUP_PATH="${BACKUP_DIR}/mongo_${DATABASE_NAME}_${TIMESTAMP}"
    DB_ARCHIVE_FILE="${DB_BACKUP_PATH}.tar.gz"

    if mongodump \
        --uri="$MONGO_URI" \
        --db="$DATABASE_NAME" \
        --out="$DB_BACKUP_PATH" \
        --gzip \
        --verbose 2>&1 | tee -a "$LOG_FILE"; then

        tar -czf "$DB_ARCHIVE_FILE" -C "$BACKUP_DIR" "$(basename "$DB_BACKUP_PATH")"
        rm -rf "$DB_BACKUP_PATH"
        log "Database ${DATABASE_NAME} backup completed: ${DB_ARCHIVE_FILE}"
    else
        log "ERROR: Backup failed for database ${DATABASE_NAME}"
        return 1
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log "Cleaning up backups older than ${RETENTION_DAYS} days"

    find "$BACKUP_DIR" -name "mongo_*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete

    REMAINING_COUNT=$(find "$BACKUP_DIR" -name "mongo_*.tar.gz" -type f | wc -l)
    log "Cleanup completed. Remaining backups: ${REMAINING_COUNT}"
}

# List all Cadence databases
list_cadence_databases() {
    MONGO_URI="mongodb://${MONGO_ROOT_USER}:${MONGO_ROOT_PASSWORD}@${MONGO_HOST}:${MONGO_PORT}"

    mongosh "$MONGO_URI" --quiet --eval "db.adminCommand('listDatabases').databases" | \
        grep -E "cadence_|admin" | \
        awk '{print $1}' | \
        sed 's/[",]//g'
}

# Send notification (optional, implement your notification method)
send_notification() {
    STATUS=$1
    MESSAGE=$2

    # Example: Send to webhook, email, or monitoring service
    # curl -X POST "https://your-webhook-url" \
    #     -H "Content-Type: application/json" \
    #     -d "{\"status\": \"$STATUS\", \"message\": \"$MESSAGE\", \"service\": \"mongo-backup\"}"

    log "Notification: ${STATUS} - ${MESSAGE}"
}

# Main execution
main() {
    log "======================================"
    log "MongoDB Backup Script Started"
    log "======================================"

    # Create backup directory if it doesn't exist
    mkdir -p "$BACKUP_DIR"

    # List databases
    log "Listing Cadence databases..."
    list_cadence_databases | tee -a "$LOG_FILE"

    # Perform backup
    if backup_mongo; then
        cleanup_old_backups
        send_notification "SUCCESS" "MongoDB backup completed successfully"
        log "Backup process completed successfully"
        exit 0
    else
        send_notification "ERROR" "MongoDB backup failed"
        log "Backup process failed"
        exit 1
    fi
}

# Run main function
main
