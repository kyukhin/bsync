#!/usr/bin/env python3
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
from datetime import datetime
from typing import Dict, Optional
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/backup_sync.log'),
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
                'source_server', 'dest_server', 'ssh_key_path', 'telegram'
            ]
            
            for key in required_keys:
                if key not in config:
                    raise ValueError(f"Missing required configuration key: {key}")
            
            # Check for either single path or directories list
            if 'directories' not in config and ('source_path' not in config or 'dest_path' not in config):
                raise ValueError("Must specify either 'directories' list or 'source_path'/'dest_path'")
            
            if 'bot_token' not in config['telegram'] or 'chat_id' not in config['telegram']:
                raise ValueError("Missing Telegram bot_token or chat_id in configuration")
            
            # Convert legacy single path format to directories format
            if 'source_path' in config and 'dest_path' in config and 'directories' not in config:
                config['directories'] = [{
                    'name': 'Main Backup',
                    'source_path': config['source_path'],
                    'dest_path': config['dest_path'],
                    'exclusions': config.get('exclusions', [])
                }]
            
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
    
    def run_rsync(self, directory_config: Dict) -> Dict:
        """Execute rsync command for a specific directory and return results"""
        start_time = datetime.now()
        
        # Build rsync command
        rsync_cmd = [
            'rsync',
            '-avz',  # archive, verbose, compress
            '--progress',
            '--stats',
            '--delete',  # delete files that don't exist in source
            '-e', f"ssh -i {self.config['ssh_key_path']} -o StrictHostKeyChecking=no",
            f"{self.config['source_server']}:{directory_config['source_path']}/",
            f"{self.config['dest_server']}:{directory_config['dest_path']}/"
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
        """Parse rsync statistics from output"""
        stats = {}
        lines = stdout.split('\n')
        
        for line in lines:
            line = line.strip()
            if 'Number of files:' in line:
                stats['total_files'] = line.split(':')[1].strip()
            elif 'Number of regular files transferred:' in line:
                stats['files_transferred'] = line.split(':')[1].strip()
            elif 'Total file size:' in line:
                size_str = line.split(':')[1].strip().split()[0]
                try:
                    stats['total_size'] = int(size_str.replace(',', ''))
                except:
                    stats['total_size'] = 0
            elif 'Total bytes sent:' in line:
                size_str = line.split(':')[1].strip().split()[0]
                try:
                    stats['bytes_sent'] = int(size_str.replace(',', ''))
                except:
                    stats['bytes_sent'] = 0
        
        return stats
    
    def send_notification(self, results: list):
        """Send Telegram notification based on sync results"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        successful_syncs = [r for r in results if r['success']]
        failed_syncs = [r for r in results if not r['success']]
        
        total_duration = sum([r['duration'] for r in results], datetime.timedelta())
        
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
                message += f"""
📂 <b>{result['directory_name']}</b>
   ⏱️ Duration: {str(result['duration']).split('.')[0]}
   🗂️ Files: {stats.get('total_files', 'N/A')}
   📊 Transferred: {stats.get('files_transferred', 'N/A')} files
   💾 Size: {self.format_size(stats.get('total_size', 0))}
   📤 Sent: {self.format_size(stats.get('bytes_sent', 0))}
"""
            
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
   📍 {self.config['source_server']}:{result['source_path']}
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
                message += f"📂 {result['directory_name']} ({stats.get('files_transferred', '0')} files)\n"
            
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
<b>Destination Server:</b> {self.config['dest_server']}
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