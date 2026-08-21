#!/usr/bin/env python3
"""
ArciTEK.AI Upgrade System
Automated updates with rollback capability and version management
"""

import os
import sys
import json
import shutil
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib

# Color codes
class Colors:
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'


class VersionManager:
    """Manages ArciTEK.AI versions and upgrades"""
    
    GITHUB_REPO = "NaTo1000/ArciTEK.AI"
    GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"
    
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.versions_dir = self.root_dir / ".versions"
        self.versions_dir.mkdir(exist_ok=True)
        
        self.version_file = self.root_dir / "VERSION"
        self.backup_dir = self.root_dir / ".backups"
        self.backup_dir.mkdir(exist_ok=True)
        
        self.current_version = self._get_current_version()
        
    def _get_current_version(self) -> str:
        """Get current installed version"""
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return "0.0.0"
    
    def _save_version(self, version: str):
        """Save version to file"""
        self.version_file.write_text(version)
    
    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.CYAN}{text.center(60)}{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")
    
    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}[ℹ]{Colors.NC} {text}")
    
    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}[✓]{Colors.NC} {text}")
    
    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}[!]{Colors.NC} {text}")
    
    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}[✗]{Colors.NC} {text}")
    
    def check_for_updates(self) -> Optional[Dict]:
        """Check for available updates from GitHub"""
        self.print_info("Checking for updates...")
        
        try:
            # Get latest release from GitHub
            response = requests.get(f"{self.GITHUB_API}/releases/latest", timeout=10)
            
            if response.status_code == 200:
                release = response.json()
                latest_version = release['tag_name'].lstrip('v')
                
                if self._compare_versions(latest_version, self.current_version) > 0:
                    return {
                        'version': latest_version,
                        'name': release['name'],
                        'body': release['body'],
                        'published_at': release['published_at'],
                        'download_url': release['zipball_url']
                    }
                else:
                    self.print_success("You are running the latest version")
                    return None
            else:
                self.print_warning("Could not check for updates (GitHub API error)")
                return None
                
        except Exception as e:
            self.print_warning(f"Could not check for updates: {e}")
            return None
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """Compare two version strings. Returns: 1 if v1>v2, -1 if v1<v2, 0 if equal"""
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        
        t1 = version_tuple(v1)
        t2 = version_tuple(v2)
        
        if t1 > t2:
            return 1
        elif t1 < t2:
            return -1
        else:
            return 0
    
    def create_backup(self) -> Path:
        """Create backup of current installation"""
        self.print_info("Creating backup of current installation...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{self.current_version}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        # Create backup directory
        backup_path.mkdir(exist_ok=True)
        
        # Files and directories to backup
        to_backup = [
            'arcitek_core',
            'quantum',
            'ai_models',
            'tools',
            'scripts',
            'config',
            'requirements.txt',
            'package.json',
            'VERSION'
        ]
        
        for item in to_backup:
            src = self.root_dir / item
            if src.exists():
                dst = backup_path / item
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
        
        # Save backup metadata
        metadata = {
            'version': self.current_version,
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat()
        }
        
        (backup_path / 'backup.json').write_text(json.dumps(metadata, indent=2))
        
        self.print_success(f"Backup created: {backup_name}")
        return backup_path
    
    def download_update(self, update_info: Dict) -> Path:
        """Download update from GitHub"""
        version = update_info['version']
        self.print_info(f"Downloading version {version}...")
        
        download_url = update_info['download_url']
        download_path = self.versions_dir / f"v{version}.zip"
        
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Progress indicator
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\r{Colors.BLUE}[●]{Colors.NC} Downloading... {progress:.1f}%", end='')
            
            print()  # New line after progress
            self.print_success(f"Downloaded {download_path.name}")
            return download_path
            
        except Exception as e:
            self.print_error(f"Download failed: {e}")
            raise
    
    def apply_update(self, update_path: Path, version: str):
        """Apply downloaded update"""
        self.print_info("Applying update...")
        
        # Extract update
        import zipfile
        
        extract_dir = self.versions_dir / f"v{version}_extracted"
        extract_dir.mkdir(exist_ok=True)
        
        with zipfile.ZipFile(update_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find the root directory (GitHub adds a prefix)
        extracted_root = next(extract_dir.iterdir())
        
        # Copy files to installation directory
        files_updated = 0
        
        for item in extracted_root.iterdir():
            if item.name in ['.git', '.github', '.backups', '.versions', 'config']:
                continue  # Skip these directories
            
            dst = self.root_dir / item.name
            
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
            
            files_updated += 1
        
        self.print_success(f"Updated {files_updated} files/directories")
        
        # Update version
        self._save_version(version)
        self.current_version = version
        
        # Clean up
        shutil.rmtree(extract_dir)
        
        self.print_success(f"Upgraded to version {version}")
    
    def run_post_upgrade_tasks(self):
        """Run post-upgrade tasks"""
        self.print_info("Running post-upgrade tasks...")
        
        tasks = []
        
        # Update Python dependencies
        if (self.root_dir / 'requirements.txt').exists():
            tasks.append(('Installing Python dependencies', 
                         ['pip3', 'install', '-q', '-r', 'requirements.txt']))
        
        # Update Node.js dependencies
        if (self.root_dir / 'package.json').exists():
            tasks.append(('Installing Node.js dependencies',
                         ['npm', 'install', '--silent']))
        
        # Run database migrations
        migration_script = self.root_dir / 'scripts' / 'migrate.py'
        if migration_script.exists():
            tasks.append(('Running database migrations',
                         ['python3', str(migration_script)]))
        
        for task_name, command in tasks:
            try:
                self.print_info(task_name)
                subprocess.run(command, cwd=self.root_dir, check=True,
                             capture_output=True)
                self.print_success(f"{task_name} completed")
            except subprocess.CalledProcessError as e:
                self.print_warning(f"{task_name} failed: {e}")
        
        self.print_success("Post-upgrade tasks completed")
    
    def list_backups(self) -> List[Dict]:
        """List available backups"""
        backups = []
        
        for backup_dir in sorted(self.backup_dir.iterdir(), reverse=True):
            if backup_dir.is_dir():
                metadata_file = backup_dir / 'backup.json'
                if metadata_file.exists():
                    metadata = json.loads(metadata_file.read_text())
                    metadata['path'] = backup_dir
                    backups.append(metadata)
        
        return backups
    
    def rollback(self, backup_path: Path):
        """Rollback to a previous backup"""
        self.print_info(f"Rolling back to backup: {backup_path.name}")
        
        # Load backup metadata
        metadata = json.loads((backup_path / 'backup.json').read_text())
        version = metadata['version']
        
        # Restore files
        for item in backup_path.iterdir():
            if item.name == 'backup.json':
                continue
            
            dst = self.root_dir / item.name
            
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
        
        # Restore version
        self._save_version(version)
        self.current_version = version
        
        self.print_success(f"Rolled back to version {version}")
    
    def upgrade(self, auto_yes: bool = False):
        """Main upgrade process"""
        self.print_header("ArciTEK.AI Upgrade System")
        
        self.print_info(f"Current version: {self.current_version}")
        
        # Check for updates
        update_info = self.check_for_updates()
        
        if not update_info:
            return 0
        
        # Display update information
        print()
        print(f"{Colors.MAGENTA}New version available: {update_info['version']}{Colors.NC}")
        print(f"{Colors.CYAN}Release: {update_info['name']}{Colors.NC}")
        print()
        print("Release notes:")
        print(update_info['body'][:500])
        if len(update_info['body']) > 500:
            print("...")
        print()
        
        # Confirm upgrade
        if not auto_yes:
            response = input(f"{Colors.YELLOW}Do you want to upgrade? (y/N): {Colors.NC}")
            if response.lower() not in ['y', 'yes']:
                self.print_info("Upgrade cancelled")
                return 0
        
        try:
            # Create backup
            backup_path = self.create_backup()
            
            # Download update
            update_path = self.download_update(update_info)
            
            # Apply update
            self.apply_update(update_path, update_info['version'])
            
            # Run post-upgrade tasks
            self.run_post_upgrade_tasks()
            
            print()
            self.print_success("Upgrade completed successfully!")
            print()
            self.print_info(f"Upgraded from {self.current_version} to {update_info['version']}")
            self.print_info(f"Backup saved to: {backup_path.name}")
            print()
            self.print_warning("Please restart ArciTEK.AI to apply changes")
            print()
            
            return 0
            
        except Exception as e:
            self.print_error(f"Upgrade failed: {e}")
            self.print_warning("Your installation was not modified")
            return 1
    
    def show_backups(self):
        """Display available backups"""
        self.print_header("Available Backups")
        
        backups = self.list_backups()
        
        if not backups:
            self.print_info("No backups found")
            return
        
        print(f"\n{Colors.CYAN}{'#':<4} {'Version':<12} {'Created':<20} {'Path'}{Colors.NC}")
        print("-" * 70)
        
        for i, backup in enumerate(backups, 1):
            created = datetime.fromisoformat(backup['created_at']).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{i:<4} {backup['version']:<12} {created:<20} {backup['path'].name}")
        
        print()
    
    def rollback_interactive(self):
        """Interactive rollback to a backup"""
        self.print_header("Rollback to Previous Version")
        
        backups = self.list_backups()
        
        if not backups:
            self.print_info("No backups available for rollback")
            return 1
        
        # Display backups
        print(f"\n{Colors.CYAN}{'#':<4} {'Version':<12} {'Created':<20}{Colors.NC}")
        print("-" * 40)
        
        for i, backup in enumerate(backups, 1):
            created = datetime.fromisoformat(backup['created_at']).strftime("%Y-%m-%d %H:%M:%S")
            print(f"{i:<4} {backup['version']:<12} {created:<20}")
        
        print()
        
        try:
            choice = input(f"{Colors.YELLOW}Select backup to restore (1-{len(backups)}) or 'q' to quit: {Colors.NC}")
            
            if choice.lower() == 'q':
                return 0
            
            index = int(choice) - 1
            
            if 0 <= index < len(backups):
                backup = backups[index]
                
                confirm = input(f"{Colors.YELLOW}Rollback to version {backup['version']}? (y/N): {Colors.NC}")
                
                if confirm.lower() in ['y', 'yes']:
                    self.rollback(backup['path'])
                    print()
                    self.print_success("Rollback completed!")
                    self.print_warning("Please restart ArciTEK.AI")
                    print()
                    return 0
            else:
                self.print_error("Invalid selection")
                return 1
                
        except (ValueError, KeyboardInterrupt):
            print()
            self.print_info("Rollback cancelled")
            return 0


def main():
    """Main entry point"""
    manager = VersionManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'check':
            manager.check_for_updates()
        elif command == 'list':
            manager.show_backups()
        elif command == 'rollback':
            sys.exit(manager.rollback_interactive())
        elif command == 'auto':
            sys.exit(manager.upgrade(auto_yes=True))
        else:
            print(f"Unknown command: {command}")
            print("Usage: upgrade.py [check|list|rollback|auto]")
            sys.exit(1)
    else:
        sys.exit(manager.upgrade())


if __name__ == "__main__":
    main()
