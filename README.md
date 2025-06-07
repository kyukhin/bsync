# Backup Synchronization Script with Telegram Notifications

A Python script that synchronizes backup data between two servers using rsync over SSH and sends status notifications via Telegram.

## Features

- 🔄 Automated rsync backup from server A to server B
- 📱 Telegram notifications for sync status (start, success, failure)
- 📊 Detailed sync statistics (files transferred, data size, duration)
- 🔒 SSH key-based authentication
- 📝 Comprehensive logging
- ⚙️ Configurable exclusions and timeouts
- 🕐 Cron job ready for daily scheduling

## Prerequisites

- Python 3.6+
- rsync installed on both servers
- SSH access between servers
- Telegram bot token and chat ID

## Quick Start

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd backup-sync
pip install -r requirements.txt
```

### 2. Create Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Save the bot token (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 3. Get Chat ID

**Method 1: Using @userinfobot**
1. Search for `@userinfobot` in Telegram
2. Send any message to get your chat ID

**Method 2: Using Telegram Web**
1. Open [web.telegram.org](https://web.telegram.org)
2. Select your chat with the bot
3. Look at the URL: `https://web.telegram.org/k/#-123456789`
4. Your chat ID is the number after `#` (including the minus sign if present)

**Method 3: Using Bot API**
1. Send a message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"chat":{"id":-123456789}` in the response

### 4. Setup SSH Keys

Generate SSH key pair if you don't have one:

```bash
ssh-keygen -t rsa -b 4096 -C "backup-sync"
```

Copy public key to both servers:

```bash
ssh-copy-id user@server-a.example.com
ssh-copy-id user@server-b.example.com
```

Test SSH connections:

```bash
ssh -i ~/.ssh/id_rsa user@server-a.example.com
ssh -i ~/.ssh/id_rsa user@server-b.example.com
```

### 5. Configure the Script

1. Copy the configuration template:
   ```bash
   # For multiple directories (recommended)
   cp config.json.template config.json
   
   # OR for single directory (simple setup)
   cp config.simple.json.template config.json
   ```

2. Edit `config.json` with your settings:

   **Multiple Directories (Recommended):**
   ```json
   {
     "source_server": "user@server-a.example.com",
     "dest_server": "user@server-b.example.com",
     "ssh_key_path": "/home/user/.ssh/id_rsa",
     "directories": [
       {
         "name": "Main Backup",
         "source_path": "/home/user/backups",
         "dest_path": "/home/user/backups",
         "exclusions": ["*.log", "*.tmp"]
       },
       {
         "name": "Documents",
         "source_path": "/home/user/documents",
         "dest_path": "/home/user/documents",
         "exclusions": ["~*", "*.tmp"]
       }
     ],
     "telegram": {
       "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
       "chat_id": "-123456789"
     },
     "timeout": 3600
   }
   ```

   **Single Directory (Legacy format):**
   ```json
   {
     "source_server": "user@server-a.example.com",
     "dest_server": "user@server-b.example.com",
     "source_path": "/home/user/backups",
     "dest_path": "/home/user/backups",
     "ssh_key_path": "/home/user/.ssh/id_rsa",
     "telegram": {
       "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
       "chat_id": "-123456789"
     },
     "exclusions": ["*.log", "*.tmp"],
     "timeout": 3600
   }
   ```

### 6. Test the Setup

Test Telegram notifications:
```bash
python backup_sync.py --test-telegram
```

Run a manual sync:
```bash
python backup_sync.py
```

## Cron Job Setup

### Daily Backup at 2 AM

1. Edit crontab:
   ```bash
   crontab -e
   ```

2. Add this line:
   ```bash
   0 2 * * * /usr/bin/python3 /path/to/backup-sync/backup_sync.py >> /var/log/backup_sync_cron.log 2>&1
   ```

### Alternative: Using a wrapper script

Create `run_backup_sync.sh`:

```bash
#!/bin/bash
cd /path/to/backup-sync
/usr/bin/python3 backup_sync.py
```

Make it executable:
```bash
chmod +x run_backup_sync.sh
```

Add to crontab:
```bash
0 2 * * * /path/to/backup-sync/run_backup_sync.sh
```

## Configuration Options

### Main Configuration

| Option | Description | Required |
|--------|-------------|----------|
| `source_server` | SSH connection to source server | Yes |
| `dest_server` | SSH connection to destination server | Yes |
| `ssh_key_path` | Path to SSH private key | Yes |
| `telegram.bot_token` | Telegram bot token | Yes |
| `telegram.chat_id` | Telegram chat ID | Yes |
| `timeout` | Rsync timeout in seconds | No (default: 3600) |

### Directory Configuration

**Multiple Directories Format:**
| Option | Description | Required |
|--------|-------------|----------|
| `directories` | Array of directory configurations | Yes |
| `directories[].name` | Friendly name for the directory | Yes |
| `directories[].source_path` | Source directory path | Yes |
| `directories[].dest_path` | Destination directory path | Yes |
| `directories[].exclusions` | Files/patterns to exclude for this directory | No |

**Legacy Single Directory Format:**
| Option | Description | Required |
|--------|-------------|----------|
| `source_path` | Source directory path | Yes |
| `dest_path` | Destination directory path | Yes |
| `exclusions` | Files/patterns to exclude | No |

## Log Files

- Main log: `/var/log/backup_sync.log`
- Cron log: `/var/log/backup_sync_cron.log`

## Troubleshooting

### Common Issues

**1. SSH Connection Failed**
```
Permission denied (publickey)
```
- Verify SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
- Test SSH connection manually
- Check if public key is in `~/.ssh/authorized_keys` on target servers

**2. Telegram Notifications Not Working**
```
Failed to send Telegram notification
```
- Verify bot token and chat ID
- Test with: `python backup_sync.py --test-telegram`
- Check if bot is blocked or chat is deleted

**3. Rsync Permission Errors**
```
rsync: recv_generator: mkdir failed: Permission denied
```
- Check destination directory permissions
- Ensure user has write access to destination path

**4. Timeout Issues**
```
Rsync command timed out
```
- Increase timeout value in config
- Check network connectivity between servers
- Monitor large file transfers

### Debugging

Enable verbose logging by modifying the script:

```python
logging.basicConfig(level=logging.DEBUG)
```

Check rsync command manually:
```bash
rsync -avz --progress --stats --delete -e "ssh -i /path/to/key" user@source:/path/ user@dest:/path/
```

## Security Considerations

1. **SSH Keys**: Use dedicated SSH keys with minimal permissions
2. **Telegram Bot**: Keep bot token secure, use environment variables if needed
3. **File Permissions**: Ensure config.json is not world-readable:
   ```bash
   chmod 600 config.json
   ```
4. **Network**: Consider using VPN or firewall rules for server connections

## Notification Examples

**Start Notification:**
```
🔄 Backup Sync Started

📅 Time: 2024-01-15 02:00:15
📁 Directories: 3

📂 Main Backup: /home/user/backups → /home/user/backups
📂 Documents: /home/user/documents → /home/user/documents
📂 Web Files: /var/www/html → /var/www/html

Source Server: user@server-a.example.com
Destination Server: user@server-b.example.com
```

**Success Notification (Multiple Directories):**
```
🟢 Backup Sync Successful

📅 Time: 2024-01-15 02:45:30
⏱️ Total Duration: 0:45:30
📁 Directories: 3

📂 Main Backup
   ⏱️ Duration: 0:25:15
   🗂️ Files: 1,234 (reg: 1,200, dir: 34)
   📊 Transferred: 25 files
   💾 Size: 2.1 GB
   📤 Sent: 85.3 MB

📂 Documents
   ⏱️ Duration: 0:12:10
   🗂️ Files: 567 (reg: 555, dir: 12) 
   📊 Transferred: 15 files
   💾 Size: 450.2 MB
   📤 Sent: 25.8 MB

📂 Web Files
   ⏱️ Duration: 0:08:05
   🗂️ Files: 890 (reg: 885, dir: 5)
   📊 Transferred: 5 files
   💾 Size: 125.7 MB
   📤 Sent: 14.6 MB
```

**Partial Success Notification:**
```
🟡 Backup Sync Partial Success

📅 Time: 2024-01-15 02:30:22
⏱️ Total Duration: 0:25:18
✅ Successful: 2
❌ Failed: 1

Successful:
📂 Main Backup (25 files)
📂 Documents (15 files)

Failed:
📂 Web Files

Please check the logs for error details.
```

**Failure Notification:**
```
🔴 Backup Sync Failed

📅 Time: 2024-01-15 02:05:22
⏱️ Total Duration: 0:05:22
📁 Failed Directories: 3

📂 Main Backup
   ❌ Error: ssh: connect to host server-b port 22: Connection refused
   📍 user@server-a:/home/user/backups

📂 Documents
   ❌ Error: Permission denied
   📍 user@server-a:/home/user/documents

📂 Web Files
   ❌ Error: No such file or directory
   📍 user@server-a:/var/www/html

Please check the logs for more details.
```

## Contributing

Feel free to submit issues and pull requests to improve the script.

## License

This project is licensed under the MIT License. 