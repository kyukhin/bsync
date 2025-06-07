#!/bin/bash

# Backup Sync Wrapper Script for Cron Jobs
# This script ensures proper environment and logging for automated backups

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/backup_sync.py"
CONFIG_FILE="$SCRIPT_DIR/config.json"
LOG_FILE="./backup_sync_cron.log"

# Function to log messages with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    log_message "ERROR: Python script not found at $PYTHON_SCRIPT"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    log_message "ERROR: Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Change to script directory
cd "$SCRIPT_DIR" || {
    log_message "ERROR: Cannot change to script directory $SCRIPT_DIR"
    exit 1
}

# Set PATH to ensure we can find Python and other tools
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Find Python 3 (prefer virtual environment)
PYTHON_CMD=""
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python3"
    log_message "Using virtual environment Python: $PYTHON_CMD"
else
    # Fallback to system Python
    for cmd in python3 python; do
        if command -v "$cmd" &> /dev/null; then
            if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3, 6) else 1)" 2>/dev/null; then
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    log_message "ERROR: Python 3.6+ not found"
    exit 1
fi

# Log start
log_message "Starting backup synchronization..."
log_message "Python command: $PYTHON_CMD"
log_message "Script directory: $SCRIPT_DIR"

# Run the backup sync
"$PYTHON_CMD" "$PYTHON_SCRIPT" 2>&1 | tee -a "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Log completion
if [ $EXIT_CODE -eq 0 ]; then
    log_message "Backup synchronization completed successfully"
else
    log_message "Backup synchronization failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE