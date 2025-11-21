# Database Backup and Restore Guide

This guide covers backup and restore procedures for the SmartFamilyTravelScout PostgreSQL database to prevent data loss and enable disaster recovery.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Manual Backup](#manual-backup)
- [Restore from Backup](#restore-from-backup)
- [Automated Backups](#automated-backups)
- [Production Backup to S3](#production-backup-to-s3)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The project uses PostgreSQL 15 with the following configuration:
- **Database name**: `travelscout`
- **Username**: `travelscout`
- **Password**: `travelscout_password`
- **Container**: `travelscout-postgres`
- **Volume**: `postgres_data`

All backup examples assume you're running PostgreSQL via Docker Compose as defined in `docker-compose.yml`.

## Prerequisites

### Required Tools

- **Docker** and **Docker Compose** (for containerized database)
- **PostgreSQL client tools** (`pg_dump`, `psql`) - installed in the container or locally
- **AWS CLI** (optional, for S3 backups)
- **cron** (optional, for automated backups)

### Verify Database Connection

Before performing backups, ensure the database is running:

```bash
# Check container status
docker-compose ps postgres

# Test database connection
docker exec travelscout-postgres pg_isready -U travelscout
```

## Manual Backup

### Basic Backup (Plain SQL Format)

Create a SQL dump file:

```bash
# Backup to local directory
docker exec travelscout-postgres pg_dump -U travelscout travelscout > backup.sql

# Backup with timestamp
docker exec travelscout-postgres pg_dump -U travelscout travelscout > "backup_$(date +%Y%m%d_%H%M%S).sql"
```

### Compressed Backup (Custom Format)

Custom format provides better compression and faster restore:

```bash
# Create compressed backup (custom format)
docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout > backup.dump

# With timestamp
docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout > "backup_$(date +%Y%m%d_%H%M%S).dump"
```

### Backup Specific Tables

```bash
# Backup only specific tables
docker exec travelscout-postgres pg_dump -U travelscout -t flights -t accommodations -t trip_packages travelscout > important_tables_backup.sql
```

### Schema-Only Backup

Useful for development or migration planning:

```bash
# Backup schema without data
docker exec travelscout-postgres pg_dump -U travelscout -s travelscout > schema_only.sql
```

### Data-Only Backup

Backup data without schema (useful for data migration):

```bash
# Backup data without schema
docker exec travelscout-postgres pg_dump -U travelscout -a travelscout > data_only.sql
```

## Restore from Backup

### Important: Pre-Restore Steps

**⚠️ WARNING**: Restoring will overwrite existing data. Always backup current data first!

```bash
# 1. Stop dependent services
docker-compose stop app celery-worker celery-beat

# 2. Create a safety backup of current data
docker exec travelscout-postgres pg_dump -U travelscout travelscout > "pre_restore_backup_$(date +%Y%m%d_%H%M%S).sql"
```

### Restore from SQL File

```bash
# Method 1: Using psql (for plain SQL backups)
docker exec -i travelscout-postgres psql -U travelscout -d travelscout < backup.sql

# Method 2: Drop and recreate database (clean restore)
docker exec travelscout-postgres psql -U travelscout -d postgres -c "DROP DATABASE IF EXISTS travelscout;"
docker exec travelscout-postgres psql -U travelscout -d postgres -c "CREATE DATABASE travelscout;"
docker exec -i travelscout-postgres psql -U travelscout -d travelscout < backup.sql
```

### Restore from Custom Format

```bash
# Restore from custom format backup
docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout -c < backup.dump

# Clean restore with verbose output
docker exec travelscout-postgres psql -U travelscout -d postgres -c "DROP DATABASE IF EXISTS travelscout;"
docker exec travelscout-postgres psql -U travelscout -d postgres -c "CREATE DATABASE travelscout;"
docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout -v < backup.dump
```

### Post-Restore Steps

```bash
# 1. Verify database integrity
docker exec travelscout-postgres psql -U travelscout -d travelscout -c "\dt"

# 2. Check row counts for critical tables
docker exec travelscout-postgres psql -U travelscout -d travelscout -c "SELECT 'flights' as table, COUNT(*) FROM flights UNION ALL SELECT 'accommodations', COUNT(*) FROM accommodations UNION ALL SELECT 'trip_packages', COUNT(*) FROM trip_packages;"

# 3. Run database migrations (if needed)
poetry run alembic upgrade head

# 4. Restart services
docker-compose start app celery-worker celery-beat
```

## Automated Backups

### Daily Cron Job (Linux/Mac)

Create a backup script and schedule it with cron:

**Step 1: Create backup script**

```bash
# Create backup directory
mkdir -p ~/backups/travelscout

# Create backup script
cat > ~/backups/travelscout/backup.sh << 'EOF'
#!/bin/bash

# Configuration
BACKUP_DIR="$HOME/backups/travelscout"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/travelscout_backup_$TIMESTAMP.dump"

# Create backup
docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout > "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Delete backups older than retention period
find "$BACKUP_DIR" -name "travelscout_backup_*.dump.gz" -mtime +$RETENTION_DAYS -delete

# Log completion
echo "$(date): Backup completed - $BACKUP_FILE.gz" >> "$BACKUP_DIR/backup.log"

# Optional: Send notification on failure
if [ $? -ne 0 ]; then
    echo "$(date): Backup FAILED" >> "$BACKUP_DIR/backup.log"
    # Add notification logic here (email, Slack, etc.)
fi
EOF

# Make script executable
chmod +x ~/backups/travelscout/backup.sh
```

**Step 2: Schedule with cron**

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /home/user/backups/travelscout/backup.sh

# Alternative schedules:
# Every 6 hours: 0 */6 * * * /home/user/backups/travelscout/backup.sh
# Weekly on Sunday at 3 AM: 0 3 * * 0 /home/user/backups/travelscout/backup.sh
```

**Step 3: Verify cron job**

```bash
# Test backup script manually
~/backups/travelscout/backup.sh

# Check backup was created
ls -lh ~/backups/travelscout/

# View backup log
cat ~/backups/travelscout/backup.log
```

## Production Backup to S3

For production environments, store backups in AWS S3 for durability and disaster recovery.

### Prerequisites

```bash
# Install AWS CLI
pip install awscli

# Configure AWS credentials
aws configure
# Enter: AWS Access Key ID, Secret Access Key, Region (e.g., eu-central-1)

# Create S3 bucket (one-time setup)
aws s3 mb s3://travelscout-backups --region eu-central-1
```

### Manual S3 Backup

```bash
# Backup and upload to S3
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout | gzip | aws s3 cp - s3://travelscout-backups/backups/travelscout_$TIMESTAMP.dump.gz

# Verify upload
aws s3 ls s3://travelscout-backups/backups/
```

### Automated S3 Backup Script

```bash
# Create S3 backup script
cat > ~/backups/travelscout/backup_s3.sh << 'EOF'
#!/bin/bash

# Configuration
S3_BUCKET="travelscout-backups"
S3_PREFIX="backups"
RETENTION_DAYS=90
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="travelscout_$TIMESTAMP.dump.gz"
LOG_FILE="$HOME/backups/travelscout/backup_s3.log"

# Create and upload backup
echo "$(date): Starting backup to S3..." >> "$LOG_FILE"

docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout | \
  gzip | \
  aws s3 cp - "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_NAME"

if [ $? -eq 0 ]; then
    echo "$(date): Backup successful - $BACKUP_NAME" >> "$LOG_FILE"

    # Delete old backups from S3
    CUTOFF_DATE=$(date -d "$RETENTION_DAYS days ago" +%Y%m%d)
    aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | while read -r line; do
        BACKUP_DATE=$(echo "$line" | awk '{print $4}' | grep -oP '\d{8}' | head -1)
        BACKUP_FILE=$(echo "$line" | awk '{print $4}')
        if [[ "$BACKUP_DATE" < "$CUTOFF_DATE" ]]; then
            aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/$BACKUP_FILE"
            echo "$(date): Deleted old backup - $BACKUP_FILE" >> "$LOG_FILE"
        fi
    done
else
    echo "$(date): Backup FAILED" >> "$LOG_FILE"
    # Add notification logic here
    exit 1
fi
EOF

# Make executable
chmod +x ~/backups/travelscout/backup_s3.sh

# Schedule daily S3 backup at 3 AM
crontab -e
# Add: 0 3 * * * /home/user/backups/travelscout/backup_s3.sh
```

### Restore from S3

```bash
# List available backups
aws s3 ls s3://travelscout-backups/backups/

# Download and restore specific backup
BACKUP_FILE="travelscout_20250121_030000.dump.gz"

# Stop services
docker-compose stop app celery-worker celery-beat

# Download and restore
aws s3 cp "s3://travelscout-backups/backups/$BACKUP_FILE" - | \
  gunzip | \
  docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout -c

# Restart services
docker-compose start app celery-worker celery-beat
```

## Best Practices

### Backup Strategy

1. **3-2-1 Rule**: Keep 3 copies of data, on 2 different media types, with 1 copy offsite
   - Primary: Live database
   - Secondary: Local daily backups
   - Tertiary: S3 backups (offsite)

2. **Retention Policy**:
   - Local backups: 30 days
   - S3 backups: 90 days
   - Critical snapshots: Store permanently before major updates

3. **Backup Frequency**:
   - Development: Daily at minimum
   - Production: Multiple times daily + before deployments

### Testing Restores

**Test your backups regularly!** A backup is only useful if it can be restored.

```bash
# Monthly restore test procedure
# 1. Create test database
docker exec travelscout-postgres psql -U travelscout -d postgres -c "CREATE DATABASE travelscout_test;"

# 2. Restore latest backup to test database
LATEST_BACKUP=$(ls -t ~/backups/travelscout/travelscout_backup_*.dump.gz | head -1)
gunzip -c "$LATEST_BACKUP" | docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout_test

# 3. Verify data integrity
docker exec travelscout-postgres psql -U travelscout -d travelscout_test -c "SELECT COUNT(*) FROM flights;"

# 4. Cleanup
docker exec travelscout-postgres psql -U travelscout -d postgres -c "DROP DATABASE travelscout_test;"
```

### Security

1. **Encrypt backups** (especially for production):
   ```bash
   # Backup with encryption
   docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout | \
     gzip | \
     openssl enc -aes-256-cbc -salt -out backup_encrypted.dump.gz.enc

   # Restore from encrypted backup
   openssl enc -aes-256-cbc -d -in backup_encrypted.dump.gz.enc | \
     gunzip | \
     docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout
   ```

2. **Secure backup storage**:
   - Restrict file permissions: `chmod 600 backup.sql`
   - Use S3 bucket encryption
   - Enable S3 versioning for backup files

3. **Protect credentials**:
   - Never commit backup files to git
   - Store AWS credentials securely
   - Use IAM roles in production instead of access keys

### Monitoring

Monitor backup success:

```bash
# Check backup log for failures
grep "FAILED" ~/backups/travelscout/backup.log

# Verify recent backups exist
ls -lht ~/backups/travelscout/ | head -5

# Check S3 backup age
aws s3 ls s3://travelscout-backups/backups/ --recursive | tail -5
```

## Troubleshooting

### Common Issues

**Problem**: `docker: command not found`
```bash
# Solution: Ensure Docker is installed and running
docker --version
docker-compose --version
```

**Problem**: `pg_dump: error: connection to server failed`
```bash
# Solution: Check if database container is running
docker-compose ps postgres
docker-compose up -d postgres
```

**Problem**: `Permission denied` when writing backup file
```bash
# Solution: Check directory permissions
mkdir -p ~/backups/travelscout
chmod 755 ~/backups/travelscout
```

**Problem**: Backup file is too large
```bash
# Solution: Use compressed custom format
docker exec travelscout-postgres pg_dump -U travelscout -Fc travelscout | gzip > backup.dump.gz

# Check size reduction
ls -lh backup.*
```

**Problem**: Restore fails with "role does not exist"
```bash
# Solution: Use --no-owner flag
gunzip -c backup.dump.gz | docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout --no-owner
```

**Problem**: S3 upload fails
```bash
# Solution: Check AWS credentials and permissions
aws sts get-caller-identity
aws s3 ls s3://travelscout-backups/

# Verify IAM permissions include: s3:PutObject, s3:GetObject, s3:ListBucket
```

### Emergency Recovery

If the database is corrupted or lost:

```bash
# 1. Stop all services
docker-compose down

# 2. Remove corrupted volume
docker volume rm smartfamilytravelscout_postgres_data

# 3. Restart database
docker-compose up -d postgres

# 4. Wait for database to initialize
sleep 10

# 5. Restore from most recent backup
LATEST_BACKUP=$(ls -t ~/backups/travelscout/travelscout_backup_*.dump.gz | head -1)
gunzip -c "$LATEST_BACKUP" | docker exec -i travelscout-postgres pg_restore -U travelscout -d travelscout

# 6. Verify restore
docker exec travelscout-postgres psql -U travelscout -d travelscout -c "\dt"

# 7. Restart all services
docker-compose up -d
```

## Additional Resources

- [PostgreSQL Backup Documentation](https://www.postgresql.org/docs/15/backup.html)
- [pg_dump Manual](https://www.postgresql.org/docs/15/app-pgdump.html)
- [pg_restore Manual](https://www.postgresql.org/docs/15/app-pgrestore.html)
- [AWS S3 CLI Reference](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/s3/index.html)

## Related Documentation

- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - Database structure and models
- [DATABASE_QUERIES.md](DATABASE_QUERIES.md) - Common database queries
- [DOCKER_SETUP.md](../DOCKER_SETUP.md) - Docker configuration details
