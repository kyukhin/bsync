#!/Users/kirillyukhin/backup-sync/venv/bin/python3
"""
Backup Synchronization Script with Telegram Notifications
Syncs backup data from server A to server B using rsync over SSH
"""

import os
import sys
import subprocess
import logging
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('./backup_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramNotifier:
    """Handle Telegram notifications"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send message to Telegram chat"""
        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode
            }
            response = requests.post(self.api_url, json=payload, timeout=30)
            response.raise_for_status()
            logger.info("Telegram notification sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

class BackupSyncer:
    """Main backup synchronization class"""

    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.telegram = TelegramNotifier(
            self.config['telegram']['bot_token'],
            self.config['telegram']['chat_id']
        )

    def load_config(self, config_path: str) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            # Validate required configuration keys
            required_keys = [
                'source_server', 'ssh_key_path', 'telegram', 'directories'
            ]

            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required configuration key: {key}")

            if 'bot_token' not in config['telegram'] or 'chat_id' not in config['telegram']:
                raise ValueError("Missing Telegram bot_token or chat_id in configuration")

            if not isinstance(config['directories'], list) or len(config['directories']) == 0:
                raise ValueError("'directories' must be a non-empty list")

            return config

        except FileNotFoundError:
            logger.error(f"Configuration file {config_path} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            sys.exit(1)

    def format_size(self, size_bytes: int) -> str:
        """Format bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def _is_valid_filename(self, filename: str) -> bool:
        """Check if a string looks like a valid filename"""
        if not filename or len(filename) > 1000:  # Sanity check for length
            return False

        # Skip strings that look like rsync progress or status output
        invalid_patterns = [
            'kB/s', 'MB/s', 'GB/s', '%', 'xfr#', 'ir-chk', 'to-chk',
            'receiving file list', 'building file list', 'speedup is',
            'delta-transmission', 'total size is', 'sent ', 'received ',
            '(DRY RUN)', 'cannot stat', 'failed to', 'error'
        ]

        filename_lower = filename.lower()
        for pattern in invalid_patterns:
            if pattern in filename_lower:
                return False

        # Skip if it's just numbers or looks like progress output
        if filename.replace(' ', '').replace('.', '').replace(':', '').isdigit():
            return False

        # Skip if it contains parentheses with transfer info
        if '(' in filename and any(x in filename for x in ['xfr#', 'ir-chk', 'to-chk']):
            return False

        return True

    def run_rsync(self, directory_config: Dict) -> Dict:
        """Execute rsync command for a specific directory and return results"""
        start_time = datetime.now()

        # Build source path (remote) and destination path (local)
        source_path = f"{self.config['source_server']}:{directory_config['source_path']}/"
        dest_path = f"{directory_config['dest_path']}/"

        # Build rsync command
        rsync_cmd = [
            'rsync',
            '-avz',  # archive, verbose, compress
            '--progress',
            '--stats',
            '--itemize-changes',  # show detailed changes for each file
            '--delete',  # delete files that don't exist in source
            '-e', f"ssh -i {self.config['ssh_key_path']} -o StrictHostKeyChecking=no",
            source_path,
            dest_path
        ]

        # Add exclusions if specified
        if 'exclusions' in directory_config:
            for exclusion in directory_config['exclusions']:
                rsync_cmd.extend(['--exclude', exclusion])

        logger.info(f"Starting rsync for {directory_config['name']}: {' '.join(rsync_cmd)}")

        try:
            # Run rsync command
            result = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=self.config.get('timeout', 3600)  # Default 1 hour timeout
            )

            end_time = datetime.now()
            duration = end_time - start_time

            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,
                'command': ' '.join(rsync_cmd),
                'directory_name': directory_config['name'],
                'source_path': directory_config['source_path'],
                'dest_path': directory_config['dest_path']
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Rsync command timed out for {directory_config['name']}")
            return {
                'success': False,
                'error': 'Timeout',
                'start_time': start_time,
                'end_time': datetime.now(),
                'duration': datetime.now() - start_time,
                'directory_name': directory_config['name'],
                'source_path': directory_config['source_path'],
                'dest_path': directory_config['dest_path']
            }
        except Exception as e:
            logger.error(f"Error running rsync for {directory_config['name']}: {e}")
            return {
                'success': False,
                'error': str(e),
                'start_time': start_time,
                'end_time': datetime.now(),
                'duration': datetime.now() - start_time,
                'directory_name': directory_config['name'],
                'source_path': directory_config['source_path'],
                'dest_path': directory_config['dest_path']
            }

    def parse_rsync_stats(self, stdout: str) -> Dict:
        """Parse rsync statistics and file changes from output"""
        stats = {}
        lines = stdout.split('\n')

        # Lists to track file operations
        added_files = []
        deleted_files = []
        updated_files = []

                # Parse each line
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines and progress output
            if not line_stripped or any(pattern in line_stripped for pattern in [
                'kB/s', 'MB/s', 'GB/s', '%', 'xfr#', 'ir-chk', 'to-chk', 'speedup is'
            ]):
                continue
            
            # Parse statistics
            if 'Number of files:' in line_stripped:
                stats['total_files'] = line_stripped.split(':')[1].strip()
            elif 'Number of regular files transferred:' in line_stripped:
                stats['files_transferred'] = line_stripped.split(':')[1].strip()
            elif 'Total file size:' in line_stripped:
                size_str = line_stripped.split(':')[1].strip().split()[0]
                try:
                    stats['total_size'] = int(size_str.replace(',', ''))
                except:
                    stats['total_size'] = 0
            elif 'Total bytes sent:' in line_stripped:
                size_str = line_stripped.split(':')[1].strip().split()[0]
                try:
                    stats['bytes_sent'] = int(size_str.replace(',', ''))
                except:
                    stats['bytes_sent'] = 0
            
            # Parse file operations (from --itemize-changes output)
            elif line_stripped.startswith('deleting ') or line_stripped.startswith('*deleting'):
                # File being deleted
                if line_stripped.startswith('*deleting'):
                    deleted_file = line_stripped[10:].strip()  # Remove "*deleting " prefix
                else:
                    deleted_file = line_stripped[9:].strip()   # Remove "deleting " prefix
                if deleted_file and not deleted_file.endswith('/') and self._is_valid_filename(deleted_file):
                    deleted_files.append(deleted_file)
            elif len(line) > 11 and line[0] in ['>', '<', '*', '.']:
                # Parse --itemize-changes output format: YXcstpoguax filename
                item_type = line[1:2]  # f=file, d=directory, L=symlink, etc.
                changes = line[2:11]   # 9 character change summary
                filename = line[11:].strip()
                
                if item_type == 'f' and filename and self._is_valid_filename(filename):
                    if '+++++++' in changes:
                        # New file (++++++++ means new)
                        added_files.append(filename)
                    elif '.' in changes and changes != '.........':
                        # Updated file (. means unchanged, other chars mean changes)
                        updated_files.append(filename)

        # Add file operation counts and lists to stats
        stats['added_files'] = added_files[:10]  # Limit to first 10 for notifications
        stats['deleted_files'] = deleted_files[:10]
        stats['updated_files'] = updated_files[:10]
        stats['added_count'] = len(added_files)
        stats['deleted_count'] = len(deleted_files)
        stats['updated_count'] = len(updated_files)

        return stats

    def send_notification(self, results: list):
        """Send Telegram notification based on sync results"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        successful_syncs = [r for r in results if r['success']]
        failed_syncs = [r for r in results if not r['success']]

        total_duration = sum([r['duration'] for r in results], timedelta())

        if len(failed_syncs) == 0:
            # All syncs successful
            message = f"""
🟢 <b>Backup Sync Successful</b>

📅 <b>Time:</b> {timestamp}
⏱️ <b>Total Duration:</b> {str(total_duration).split('.')[0]}
📁 <b>Directories:</b> {len(results)}

"""

            for result in successful_syncs:
                stats = self.parse_rsync_stats(result.get('stdout', ''))

                # Build file changes summary
                changes_summary = ""
                if stats.get('added_count', 0) > 0:
                    changes_summary += f"   ➕ Added: {stats['added_count']} files\n"
                    if stats.get('added_files'):
                        sample_files = stats['added_files'][:3]  # Show first 3
                        for file in sample_files:
                            changes_summary += f"      • {file}\n"
                        if stats['added_count'] > 3:
                            changes_summary += f"      ... and {stats['added_count'] - 3} more\n"

                if stats.get('updated_count', 0) > 0:
                    changes_summary += f"   🔄 Updated: {stats['updated_count']} files\n"
                    if stats.get('updated_files'):
                        sample_files = stats['updated_files'][:3]  # Show first 3
                        for file in sample_files:
                            changes_summary += f"      • {file}\n"
                        if stats['updated_count'] > 3:
                            changes_summary += f"      ... and {stats['updated_count'] - 3} more\n"

                if stats.get('deleted_count', 0) > 0:
                    changes_summary += f"   🗑️ Deleted: {stats['deleted_count']} files\n"
                    if stats.get('deleted_files'):
                        sample_files = stats['deleted_files'][:3]  # Show first 3
                        for file in sample_files:
                            changes_summary += f"      • {file}\n"
                        if stats['deleted_count'] > 3:
                            changes_summary += f"      ... and {stats['deleted_count'] - 3} more\n"

                if not changes_summary:
                    changes_summary = "   ✅ No changes (files up to date)\n"

                message += f"""
📂 <b>{result['directory_name']}</b>
   ⏱️ Duration: {str(result['duration']).split('.')[0]}
   🗂️ Files: {stats.get('total_files', 'N/A')}
   📊 Transferred: {stats.get('files_transferred', 'N/A')} files
   💾 Size: {self.format_size(stats.get('total_size', 0))}
   📤 Sent: {self.format_size(stats.get('bytes_sent', 0))}
{changes_summary}"""

        elif len(successful_syncs) == 0:
            # All syncs failed
            message = f"""
🔴 <b>Backup Sync Failed</b>

📅 <b>Time:</b> {timestamp}
⏱️ <b>Total Duration:</b> {str(total_duration).split('.')[0]}
📁 <b>Failed Directories:</b> {len(failed_syncs)}

"""

            for result in failed_syncs[:3]:  # Show first 3 failures
                error_msg = result.get('stderr', result.get('error', 'Unknown error'))
                message += f"""
📂 <b>{result['directory_name']}</b>
   ❌ Error: {error_msg[:200]}
   📍 {self.config['source_server']}:{result['source_path']} → local:{result['dest_path']}
"""

            if len(failed_syncs) > 3:
                message += f"\n... and {len(failed_syncs) - 3} more failures"

            message += "\nPlease check the logs for more details."

        else:
            # Mixed results
            message = f"""
🟡 <b>Backup Sync Partial Success</b>

📅 <b>Time:</b> {timestamp}
⏱️ <b>Total Duration:</b> {str(total_duration).split('.')[0]}
✅ <b>Successful:</b> {len(successful_syncs)}
❌ <b>Failed:</b> {len(failed_syncs)}

<b>Successful:</b>
"""

            for result in successful_syncs:
                stats = self.parse_rsync_stats(result.get('stdout', ''))
                changes_info = ""
                if stats.get('added_count', 0) > 0:
                    changes_info += f"+{stats['added_count']} "
                if stats.get('updated_count', 0) > 0:
                    changes_info += f"~{stats['updated_count']} "
                if stats.get('deleted_count', 0) > 0:
                    changes_info += f"-{stats['deleted_count']} "
                changes_info = changes_info.strip() or "no changes"
                message += f"📂 {result['directory_name']} ({changes_info})\n"

            message += "\n<b>Failed:</b>\n"
            for result in failed_syncs:
                message += f"📂 {result['directory_name']}\n"

            message += "\nPlease check the logs for error details."

        self.telegram.send_message(message)

    def sync(self):
        """Main sync function"""
        logger.info("Starting backup synchronization")

        # Send start notification
        directories_list = "\n".join([f"📂 {d['name']}: {d['source_path']} → {d['dest_path']}"
                                     for d in self.config['directories']])

        start_message = f"""
🔄 <b>Backup Sync Started</b>

📅 <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
📁 <b>Directories:</b> {len(self.config['directories'])}

{directories_list}

<b>Source Server:</b> {self.config['source_server']}
"""
        self.telegram.send_message(start_message)

        # Run rsync for each directory
        results = []
        overall_success = True

        for directory in self.config['directories']:
            logger.info(f"Starting sync for directory: {directory['name']}")
            result = self.run_rsync(directory)
            results.append(result)

            if result['success']:
                logger.info(f"Successfully synced directory: {directory['name']}")
            else:
                logger.error(f"Failed to sync directory {directory['name']}: {result.get('stderr', result.get('error'))}")
                overall_success = False

        # Log overall result
        if overall_success:
            logger.info("All backup synchronizations completed successfully")
        else:
            failed_dirs = [r['directory_name'] for r in results if not r['success']]
            logger.error(f"Backup synchronization failed for directories: {', '.join(failed_dirs)}")

        # Send completion notification
        self.send_notification(results)

        return overall_success

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Backup Synchronization Script')
    parser.add_argument('--config', default='config.json', help='Configuration file path')
    parser.add_argument('--test-telegram', action='store_true', help='Test Telegram notification')

    args = parser.parse_args()

    try:
        syncer = BackupSyncer(args.config)

        if args.test_telegram:
            # Test Telegram notification
            test_message = f"""
🧪 <b>Test Notification</b>

📅 <b>Time:</b> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This is a test message from the backup sync script.
If you can see this, Telegram notifications are working correctly! ✅
"""
            success = syncer.telegram.send_message(test_message)
            if success:
                print("✅ Telegram test notification sent successfully!")
            else:
                print("❌ Failed to send Telegram test notification")
            return

        # Run sync
        success = syncer.sync()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Backup synchronization interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()