#!/bin/bash

# Backup Sync Installation Script
# This script helps set up the backup synchronization system

set -e  # Exit on any error

echo "🚀 Backup Sync Installation Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root for certain operations
NEED_SUDO=false

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Python 3.6+
print_info "Checking Python installation..."
if command_exists python3; then
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 6) else 1)" 2>/dev/null; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python 3.6+ is required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python 3.6+ first."
    exit 1
fi

# Check pip
print_info "Checking pip installation..."
if command_exists pip3; then
    print_success "pip3 found"
elif command_exists pip; then
    if pip --version | grep -q "python 3"; then
        print_success "pip (Python 3) found"
    else
        print_error "pip for Python 3 not found"
        exit 1
    fi
else
    print_error "pip not found. Please install pip first."
    exit 1
fi

# Check rsync
print_info "Checking rsync installation..."
if command_exists rsync; then
    RSYNC_VERSION=$(rsync --version | head -n1)
    print_success "rsync found: $RSYNC_VERSION"
else
    print_warning "rsync not found. Please install rsync:"
    echo "  - Ubuntu/Debian: sudo apt install rsync"
    echo "  - CentOS/RHEL: sudo yum install rsync"
    echo "  - macOS: brew install rsync"
fi

# Create and activate virtual environment
print_info "Setting up Python virtual environment..."
if python3 -m venv venv; then
    print_success "Virtual environment created"
else
    print_error "Failed to create virtual environment"
    exit 1
fi

# Activate virtual environment and install dependencies
print_info "Installing Python dependencies in virtual environment..."
if source venv/bin/activate && pip install -r requirements.txt; then
    print_success "Python dependencies installed in virtual environment"
else
    print_error "Failed to install Python dependencies"
    exit 1
fi

# Create configuration file
print_info "Setting up configuration..."
if [ ! -f "config.json" ]; then
    if [ -f "config.json.template" ]; then
        cp config.json.template config.json
        chmod 600 config.json
        print_success "Configuration file created from template"
        print_warning "Please edit config.json with your server details and Telegram credentials"
    else
        print_error "Configuration template not found!"
        exit 1
    fi
else
    print_warning "config.json already exists, skipping template copy"
fi

# Update scripts to use virtual environment Python
print_info "Configuring scripts to use virtual environment..."
sed -i.bak "1s|.*|#!$(pwd)/venv/bin/python3|" backup_sync.py
chmod +x backup_sync.py run_backup_sync.sh
print_success "Scripts configured and made executable"

# Create log directory
print_info "Setting up logging..."
if [ -w "/var/log" ] || sudo -n true 2>/dev/null; then
    if [ ! -w "/var/log" ]; then
        sudo touch /var/log/backup_sync.log /var/log/backup_sync_cron.log
        sudo chown $USER:$USER /var/log/backup_sync.log /var/log/backup_sync_cron.log
    else
        touch /var/log/backup_sync.log /var/log/backup_sync_cron.log
    fi
    print_success "Log files created in /var/log/"
else
    print_warning "Cannot write to /var/log, logs will be created in current directory"
    # Modify the script to use local logging
    sed -i.bak 's|/var/log/backup_sync.log|./backup_sync.log|g' backup_sync.py
    sed -i.bak 's|/var/log/backup_sync_cron.log|./backup_sync_cron.log|g' run_backup_sync.sh
    print_info "Updated log paths to use current directory"
fi

# Test configuration
print_info "Testing configuration..."
if [ -f "config.json" ]; then
    # Simple JSON validation
    if python3 -c "import json; json.load(open('config.json'))" 2>/dev/null; then
        print_success "Configuration file is valid JSON"
    else
        print_error "Configuration file has invalid JSON syntax"
        exit 1
    fi
else
    print_error "Configuration file not found"
    exit 1
fi

echo ""
echo "🎉 Installation completed successfully!"
echo ""
echo "Next steps:"
echo "==========="
echo "1. Edit config.json with your server details:"
echo "   - Server hostnames/IPs and paths"
echo "   - SSH key path"
echo "   - Telegram bot token and chat ID"
echo ""
echo "2. Test Telegram notifications:"
echo "   ./backup_sync.py --test-telegram"
echo ""
echo "3. Run a manual backup test:"
echo "   ./backup_sync.py"
echo ""
echo "4. Set up daily cron job:"
echo "   crontab -e"
echo "   Add: 0 2 * * * $(pwd)/run_backup_sync.sh"
echo ""
echo "For detailed setup instructions, see README.md"

# Check if SSH key exists
if [ -f "$HOME/.ssh/id_rsa" ]; then
    print_success "SSH key found at $HOME/.ssh/id_rsa"
else
    print_warning "No SSH key found. You may need to generate one:"
    echo "   ssh-keygen -t rsa -b 4096 -C 'backup-sync'"
fi

echo ""
print_info "Installation log saved in /tmp/backup_sync_install.log"