# Logging Configuration and Rotation

This document describes the logging configuration and log rotation features of SmartFamilyTravelScout.

## Overview

The application uses Python's built-in logging module with structured logging support. Logs can be formatted as JSON (for production) or human-readable format (for development).

**Key Features:**
- Automatic log rotation to prevent disk space exhaustion
- Configurable rotation size and backup count
- JSON and colored console formatters
- Multiple rotation strategies (application-level and system-level)

## Application-Level Log Rotation

The application automatically rotates logs using Python's `RotatingFileHandler`.

### Default Settings

- **Max file size**: 10MB (configurable)
- **Backup count**: 5 files (configurable)
- **Format**: JSON for files, colored for console

When a log file reaches 10MB, it's automatically renamed with a numeric suffix (e.g., `app.log.1`, `app.log.2`) and a new log file is created. The oldest backup is deleted when the backup count is exceeded.

### Configuration

You can configure rotation settings via environment variables:

```bash
# .env file
LOG_MAX_BYTES=10485760  # 10MB - Maximum size before rotation
LOG_BACKUP_COUNT=5      # Number of backup files to keep
```

Or in code using `setup_logging()`:

```python
from app.utils.logging_config import setup_logging

# Setup with custom rotation
setup_logging(
    level="INFO",
    log_file="logs/app.log",
    max_bytes=52428800,   # 50MB
    backup_count=10       # Keep 10 backups
)
```

### Log Files

The application creates these log files:

- `logs/app.log` - Main application log (all levels)
- `logs/error.log` - Error-level logs only

Each file rotates independently based on size.

## System-Level Log Rotation (Linux)

For production deployments on Linux, you can use the `logrotate` utility for system-level rotation.

### Setup

1. Copy the logrotate configuration:
```bash
sudo cp deployment/logrotate.conf /etc/logrotate.d/smartfamilytravelscout
```

2. Create log directory:
```bash
sudo mkdir -p /var/log/smartfamilytravelscout
sudo chown -R <app-user>:<app-group> /var/log/smartfamilytravelscout
```

3. Test the configuration:
```bash
sudo logrotate -d /etc/logrotate.d/smartfamilytravelscout
```

### Logrotate Settings

The provided configuration (`deployment/logrotate.conf`) uses:

- **Rotation**: Daily
- **Retention**: 7 days for app logs, 30 days for error logs
- **Compression**: Yes (gzip)
- **Max size**: 10MB (rotates immediately if exceeded)

### Customization

Edit `/etc/logrotate.d/smartfamilytravelscout` to customize:

```conf
/var/log/smartfamilytravelscout/*.log {
    daily           # Change to: weekly, monthly
    rotate 7        # Change to: 14, 30, etc.
    size 10M        # Change to: 50M, 100M, etc.
    # ... other options
}
```

## Choosing a Rotation Strategy

### Application-Level (Python RotatingFileHandler)

**Pros:**
- No system dependencies
- Works on all platforms (Windows, Linux, macOS)
- Immediate rotation when size exceeded
- No root/sudo access needed

**Cons:**
- Less flexible scheduling (size-based only)
- Can't compress old logs
- Requires application restart to change settings

**Best for:**
- Development environments
- Docker/containerized deployments
- Cross-platform applications
- Quick setup

### System-Level (logrotate)

**Pros:**
- Flexible scheduling (daily, weekly, monthly)
- Compression support
- Can run custom scripts after rotation
- Centralized log management
- Works even if application is stopped

**Cons:**
- Linux-only
- Requires root/sudo access to configure
- Needs system administration knowledge

**Best for:**
- Production Linux servers
- Long-term log retention
- Compliance requirements
- Integration with system monitoring

### Hybrid Approach (Recommended for Production)

Use **both** strategies together:

1. **Application-level**: As safety net for rapid log growth
   - Set higher thresholds (e.g., 50MB, 10 backups)

2. **System-level**: For scheduled rotation and compression
   - Daily rotation with compression
   - Long-term retention policy

This ensures logs are rotated both by size (application) and time (system).

## Logging Best Practices

### File Size Guidelines

- **Development**: 10MB max, 5 backups (default)
- **Production**: 50-100MB max, 10-20 backups
- **High-traffic**: Use system-level rotation with compression

### Retention Guidelines

Based on your needs:

- **Debug/Development**: 3-7 days
- **Production**: 14-30 days
- **Error logs**: 30-90 days
- **Compliance**: 1-7 years (with archival)

### Performance Considerations

Log rotation doesn't block the application, but consider:

1. **Size threshold**: Smaller files = more frequent rotation
2. **Backup count**: More backups = more disk space
3. **Compression**: Saves space but uses CPU

## Monitoring Log Rotation

### Check Rotation Status

```bash
# View log files and sizes
ls -lh logs/

# Check if rotation is working
ls -lh logs/app.log*

# View logrotate status
cat /var/lib/logrotate/status | grep smartfamilytravelscout
```

### Testing Rotation

#### Application-level

```python
from app.utils.logging_config import setup_logging
import logging

# Setup with small size for testing
setup_logging(
    level="INFO",
    log_file="logs/test.log",
    max_bytes=1024,  # 1KB
    backup_count=3
)

# Generate logs to trigger rotation
for i in range(100):
    logging.info(f"Test message {i}" * 50)

# Check created files
# ls -lh logs/test.log*
```

#### System-level

```bash
# Dry run (shows what would happen)
sudo logrotate -d /etc/logrotate.d/smartfamilytravelscout

# Force rotation (for testing)
sudo logrotate -f /etc/logrotate.d/smartfamilytravelscout

# Check results
ls -lh /var/log/smartfamilytravelscout/
```

## Troubleshooting

### Logs Not Rotating

**Application-level:**
- Check file permissions on log directory
- Verify `max_bytes` is set correctly
- Ensure application has write access

**System-level:**
- Check logrotate configuration syntax
- Verify log file paths match
- Check system cron is running
- Review logrotate errors: `sudo cat /var/log/syslog | grep logrotate`

### Disk Space Issues

If logs are consuming too much space:

1. Reduce `backup_count` or `rotate` days
2. Enable compression (system-level)
3. Reduce `max_bytes` / `size` threshold
4. Archive old logs to external storage

### Permission Errors

```bash
# Fix log directory permissions
sudo chown -R <app-user>:<app-group> /var/log/smartfamilytravelscout
sudo chmod 755 /var/log/smartfamilytravelscout
sudo chmod 644 /var/log/smartfamilytravelscout/*.log
```

## Examples

### Example 1: Development Setup

```python
from app.utils.logging_config import setup_logging

setup_logging(
    level="DEBUG",
    json_format=False,
    log_file="logs/dev.log",
    max_bytes=10485760,  # 10MB
    backup_count=3
)
```

### Example 2: Production Setup

```python
from app.utils.logging_config import setup_logging

setup_logging(
    level="INFO",
    json_format=True,
    log_file="/var/log/smartfamilytravelscout/app.log",
    max_bytes=52428800,  # 50MB
    backup_count=20
)
```

### Example 3: High-Volume Production

Use system-level rotation:

```conf
# /etc/logrotate.d/smartfamilytravelscout
/var/log/smartfamilytravelscout/*.log {
    hourly          # Rotate every hour
    rotate 168      # Keep 1 week (24 * 7)
    compress
    delaycompress
    size 100M       # Also rotate if exceeds 100MB
    sharedscripts
}
```

## See Also

- `app/utils/logging_config.py` - Application logging implementation
- `app/__init__.py` - Application initialization with logging
- `deployment/logrotate.conf` - System-level rotation configuration
- `.env.example` - Environment variable examples
