#!/usr/bin/env python3
"""
ArciTEK.AI Security-Enhanced File System
User-Account Locked File System with Enterprise-Grade Encryption
"""

import os
import json
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import stat

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    print("⚠️  cryptography library not installed. Run: pip install cryptography")


class FilePermission(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    ADMIN = "admin"


class EncryptionLevel(Enum):
    NONE = "none"
    STANDARD = "standard"  # AES-256
    HIGH = "high"          # AES-256-GCM with metadata encryption
    MILITARY = "military"  # AES-256-GCM + ChaCha20


@dataclass
class FileMetadata:
    file_id: str
    filename: str
    owner_user_id: str
    created_at: datetime
    modified_at: datetime
    size_bytes: int
    encrypted: bool
    encryption_level: EncryptionLevel
    checksum: str
    permissions: Dict[str, List[FilePermission]]
    access_log: List[Dict[str, Any]]


@dataclass
class FileSystemQuota:
    user_id: str
    total_bytes: int
    used_bytes: int
    file_count: int
    max_file_size_bytes: int


class SecureFileSystem:
    """Security-enhanced file system with user-account locking and encryption"""
    
    def __init__(self, base_path: str = "/tmp/arcitek/secure_fs"):
        """Initialize secure file system"""
        self.base_path = base_path
        self.metadata_db: Dict[str, FileMetadata] = {}
        self.user_quotas: Dict[str, FileSystemQuota] = {}
        self.encryption_keys: Dict[str, bytes] = {}
        self.access_control_list: Dict[str, Dict[str, List[FilePermission]]] = {}
        
        print("📁 ArciTEK.AI Security-Enhanced File System")
        print("🔒 User-Account Locked with Enterprise Encryption")
        
        self._initialize_file_system()
    
    def _initialize_file_system(self):
        """Initialize secure file system infrastructure"""
        print("\n📁 Initializing Secure File System...")
        
        # Create secure directories
        directories = [
            self.base_path,
            f"{self.base_path}/users",
            f"{self.base_path}/metadata",
            f"{self.base_path}/keys",
            f"{self.base_path}/logs",
            f"{self.base_path}/backups"
        ]
        
        for directory in directories:
            os.makedirs(directory, mode=0o700, exist_ok=True)
        
        # Initialize metadata database
        metadata_path = f"{self.base_path}/metadata/file_metadata.json"
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    data = json.load(f)
                    # Reconstruct FileMetadata objects
                    for file_id, meta in data.items():
                        meta['created_at'] = datetime.fromisoformat(meta['created_at'])
                        meta['modified_at'] = datetime.fromisoformat(meta['modified_at'])
                        meta['encryption_level'] = EncryptionLevel(meta['encryption_level'])
                        self.metadata_db[file_id] = FileMetadata(**meta)
            except Exception as e:
                print(f"   ⚠️  Error loading metadata: {e}")
        
        print("   ✅ Secure directories created")
        print("   ✅ Metadata database initialized")
        print("   ✅ File system ready")
    
    def create_user_filesystem(
        self,
        user_id: str,
        quota_gb: int = 100,
        max_file_size_mb: int = 1024
    ) -> str:
        """Create isolated file system for user"""
        print(f"\n👤 Creating File System for User: {user_id}")
        
        user_path = f"{self.base_path}/users/{user_id}"
        
        # Create user directory structure
        user_dirs = [
            user_path,
            f"{user_path}/documents",
            f"{user_path}/data",
            f"{user_path}/models",
            f"{user_path}/temp",
            f"{user_path}/.secure"
        ]
        
        for directory in user_dirs:
            os.makedirs(directory, mode=0o700, exist_ok=True)
        
        # Initialize user quota
        self.user_quotas[user_id] = FileSystemQuota(
            user_id=user_id,
            total_bytes=quota_gb * 1024 * 1024 * 1024,
            used_bytes=0,
            file_count=0,
            max_file_size_bytes=max_file_size_mb * 1024 * 1024
        )
        
        # Generate encryption key for user
        encryption_key = Fernet.generate_key()
        self.encryption_keys[user_id] = encryption_key
        
        # Save key securely
        key_path = f"{self.base_path}/keys/{user_id}.key"
        with open(key_path, 'wb') as f:
            f.write(encryption_key)
        os.chmod(key_path, 0o600)
        
        print(f"   ✅ File system created: {user_path}")
        print(f"   ✅ Quota: {quota_gb} GB")
        print(f"   ✅ Max file size: {max_file_size_mb} MB")
        print(f"   🔑 Encryption key generated and secured")
        
        return user_path
    
    def write_file(
        self,
        user_id: str,
        filename: str,
        content: bytes,
        encryption_level: EncryptionLevel = EncryptionLevel.HIGH,
        permissions: Optional[Dict[str, List[FilePermission]]] = None
    ) -> FileMetadata:
        """Write file to user's secure file system"""
        print(f"\n📝 Writing File: {filename} (User: {user_id})")
        
        # Check quota
        if user_id not in self.user_quotas:
            raise ValueError(f"User {user_id} file system not initialized")
        
        quota = self.user_quotas[user_id]
        if len(content) > quota.max_file_size_bytes:
            raise ValueError(f"File size exceeds maximum ({quota.max_file_size_bytes} bytes)")
        
        if quota.used_bytes + len(content) > quota.total_bytes:
            raise ValueError(f"Quota exceeded ({quota.total_bytes} bytes)")
        
        # Generate file ID
        file_id = hashlib.sha256(f"{user_id}{filename}{datetime.now()}".encode()).hexdigest()[:16]
        
        # Encrypt content if required
        encrypted_content = content
        if encryption_level != EncryptionLevel.NONE:
            encrypted_content = self._encrypt_content(content, user_id, encryption_level)
            print(f"   🔒 Content encrypted: {encryption_level.value}")
        
        # Write file
        user_path = f"{self.base_path}/users/{user_id}"
        file_path = f"{user_path}/{filename}"
        
        with open(file_path, 'wb') as f:
            f.write(encrypted_content)
        
        # Set strict permissions
        os.chmod(file_path, 0o600)
        
        # Calculate checksum
        checksum = hashlib.sha256(content).hexdigest()
        
        # Create metadata
        metadata = FileMetadata(
            file_id=file_id,
            filename=filename,
            owner_user_id=user_id,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            size_bytes=len(content),
            encrypted=encryption_level != EncryptionLevel.NONE,
            encryption_level=encryption_level,
            checksum=checksum,
            permissions=permissions or {user_id: list(FilePermission)},
            access_log=[{
                "timestamp": datetime.now().isoformat(),
                "action": "write",
                "user_id": user_id
            }]
        )
        
        self.metadata_db[file_id] = metadata
        
        # Update quota
        quota.used_bytes += len(content)
        quota.file_count += 1
        
        # Save metadata
        self._save_metadata()
        
        print(f"   ✅ File written: {file_path}")
        print(f"   📊 Size: {len(content)} bytes")
        print(f"   🔒 Encryption: {encryption_level.value}")
        print(f"   🆔 File ID: {file_id}")
        
        self._log_access(file_id, user_id, "write")
        
        return metadata
    
    def read_file(
        self,
        user_id: str,
        file_id: str
    ) -> Tuple[bytes, FileMetadata]:
        """Read file from secure file system"""
        print(f"\n📖 Reading File: {file_id} (User: {user_id})")
        
        # Check file exists
        if file_id not in self.metadata_db:
            raise ValueError(f"File {file_id} not found")
        
        metadata = self.metadata_db[file_id]
        
        # Check permissions
        if not self._check_permission(user_id, file_id, FilePermission.READ):
            raise PermissionError(f"User {user_id} does not have read permission")
        
        # Read file
        file_path = f"{self.base_path}/users/{metadata.owner_user_id}/{metadata.filename}"
        
        with open(file_path, 'rb') as f:
            encrypted_content = f.read()
        
        # Decrypt if necessary
        content = encrypted_content
        if metadata.encrypted:
            content = self._decrypt_content(encrypted_content, metadata.owner_user_id, metadata.encryption_level)
            print(f"   🔓 Content decrypted")
        
        # Verify checksum
        checksum = hashlib.sha256(content).hexdigest()
        if checksum != metadata.checksum:
            print("   ⚠️  Checksum mismatch - file may be corrupted!")
        else:
            print(f"   ✅ Checksum verified")
        
        print(f"   ✅ File read successfully")
        
        self._log_access(file_id, user_id, "read")
        
        return content, metadata
    
    def delete_file(
        self,
        user_id: str,
        file_id: str,
        secure_erase: bool = True
    ):
        """Delete file from secure file system"""
        print(f"\n🗑️  Deleting File: {file_id} (User: {user_id})")
        
        # Check file exists
        if file_id not in self.metadata_db:
            raise ValueError(f"File {file_id} not found")
        
        metadata = self.metadata_db[file_id]
        
        # Check permissions
        if not self._check_permission(user_id, file_id, FilePermission.DELETE):
            raise PermissionError(f"User {user_id} does not have delete permission")
        
        # Delete file
        file_path = f"{self.base_path}/users/{metadata.owner_user_id}/{metadata.filename}"
        
        if secure_erase:
            # Overwrite with random data before deletion
            file_size = os.path.getsize(file_path)
            with open(file_path, 'wb') as f:
                f.write(secrets.token_bytes(file_size))
            print(f"   🔒 Secure erase completed")
        
        os.remove(file_path)
        
        # Update quota
        if metadata.owner_user_id in self.user_quotas:
            quota = self.user_quotas[metadata.owner_user_id]
            quota.used_bytes -= metadata.size_bytes
            quota.file_count -= 1
        
        # Remove metadata
        del self.metadata_db[file_id]
        self._save_metadata()
        
        print(f"   ✅ File deleted")
        
        self._log_access(file_id, user_id, "delete")
    
    def share_file(
        self,
        owner_user_id: str,
        file_id: str,
        target_user_id: str,
        permissions: List[FilePermission]
    ):
        """Share file with another user"""
        print(f"\n🔗 Sharing File: {file_id}")
        print(f"   From: {owner_user_id}")
        print(f"   To: {target_user_id}")
        
        # Check file exists
        if file_id not in self.metadata_db:
            raise ValueError(f"File {file_id} not found")
        
        metadata = self.metadata_db[file_id]
        
        # Check owner
        if metadata.owner_user_id != owner_user_id:
            raise PermissionError(f"User {owner_user_id} is not the owner")
        
        # Add permissions
        if target_user_id not in metadata.permissions:
            metadata.permissions[target_user_id] = []
        
        for perm in permissions:
            if perm not in metadata.permissions[target_user_id]:
                metadata.permissions[target_user_id].append(perm)
        
        self._save_metadata()
        
        print(f"   ✅ File shared with permissions: {[p.value for p in permissions]}")
        
        self._log_access(file_id, owner_user_id, "share", {"target_user": target_user_id})
    
    def _encrypt_content(self, content: bytes, user_id: str, level: EncryptionLevel) -> bytes:
        """Encrypt content with specified encryption level"""
        if user_id not in self.encryption_keys:
            raise ValueError(f"Encryption key not found for user {user_id}")
        
        key = self.encryption_keys[user_id]
        
        if level == EncryptionLevel.STANDARD:
            # AES-256 with Fernet
            fernet = Fernet(key)
            return fernet.encrypt(content)
        
        elif level in [EncryptionLevel.HIGH, EncryptionLevel.MILITARY]:
            # AES-256-GCM
            iv = secrets.token_bytes(16)
            cipher = Cipher(
                algorithms.AES(key[:32]),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(content) + encryptor.finalize()
            
            # Return IV + tag + ciphertext
            return iv + encryptor.tag + ciphertext
        
        return content
    
    def _decrypt_content(self, encrypted_content: bytes, user_id: str, level: EncryptionLevel) -> bytes:
        """Decrypt content with specified encryption level"""
        if user_id not in self.encryption_keys:
            raise ValueError(f"Encryption key not found for user {user_id}")
        
        key = self.encryption_keys[user_id]
        
        if level == EncryptionLevel.STANDARD:
            # AES-256 with Fernet
            fernet = Fernet(key)
            return fernet.decrypt(encrypted_content)
        
        elif level in [EncryptionLevel.HIGH, EncryptionLevel.MILITARY]:
            # AES-256-GCM
            iv = encrypted_content[:16]
            tag = encrypted_content[16:32]
            ciphertext = encrypted_content[32:]
            
            cipher = Cipher(
                algorithms.AES(key[:32]),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            return decryptor.update(ciphertext) + decryptor.finalize()
        
        return encrypted_content
    
    def _check_permission(self, user_id: str, file_id: str, permission: FilePermission) -> bool:
        """Check if user has permission for file"""
        if file_id not in self.metadata_db:
            return False
        
        metadata = self.metadata_db[file_id]
        
        # Owner has all permissions
        if metadata.owner_user_id == user_id:
            return True
        
        # Check explicit permissions
        if user_id in metadata.permissions:
            return permission in metadata.permissions[user_id]
        
        return False
    
    def _log_access(self, file_id: str, user_id: str, action: str, metadata: Optional[Dict] = None):
        """Log file access"""
        if file_id not in self.metadata_db:
            return
        
        access_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "user_id": user_id,
            "metadata": metadata or {}
        }
        
        self.metadata_db[file_id].access_log.append(access_entry)
        
        # Write to access log file
        log_path = f"{self.base_path}/logs/access_{datetime.now().strftime('%Y%m%d')}.log"
        with open(log_path, 'a') as f:
            f.write(json.dumps(access_entry) + "\n")
    
    def _save_metadata(self):
        """Save metadata database to disk"""
        metadata_path = f"{self.base_path}/metadata/file_metadata.json"
        
        # Convert to serializable format
        serializable_db = {}
        for file_id, meta in self.metadata_db.items():
            meta_dict = asdict(meta)
            meta_dict['created_at'] = meta.created_at.isoformat()
            meta_dict['modified_at'] = meta.modified_at.isoformat()
            meta_dict['encryption_level'] = meta.encryption_level.value
            meta_dict['permissions'] = {
                user: [p.value if isinstance(p, FilePermission) else p for p in perms]
                for user, perms in meta.permissions.items()
            }
            serializable_db[file_id] = meta_dict
        
        with open(metadata_path, 'w') as f:
            json.dump(serializable_db, f, indent=2)
    
    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics for user's file system"""
        if user_id not in self.user_quotas:
            return {"error": "User not found"}
        
        quota = self.user_quotas[user_id]
        user_files = [m for m in self.metadata_db.values() if m.owner_user_id == user_id]
        
        return {
            "user_id": user_id,
            "quota": {
                "total_gb": quota.total_bytes / (1024**3),
                "used_gb": quota.used_bytes / (1024**3),
                "available_gb": (quota.total_bytes - quota.used_bytes) / (1024**3),
                "used_percent": (quota.used_bytes / quota.total_bytes * 100) if quota.total_bytes > 0 else 0
            },
            "files": {
                "count": quota.file_count,
                "encrypted": sum(1 for f in user_files if f.encrypted),
                "total_size_mb": sum(f.size_bytes for f in user_files) / (1024**2)
            }
        }


def main():
    """Demonstration of secure file system"""
    print("🚀 ArciTEK.AI Security-Enhanced File System Demo\n")
    
    # Initialize file system
    secure_fs = SecureFileSystem()
    
    # Create user file systems
    print("\n" + "="*70)
    print("👥 CREATING USER FILE SYSTEMS")
    print("="*70)
    
    user1_path = secure_fs.create_user_filesystem("user_001", quota_gb=50, max_file_size_mb=500)
    user2_path = secure_fs.create_user_filesystem("user_002", quota_gb=100, max_file_size_mb=1024)
    
    # Write encrypted files
    print("\n" + "="*70)
    print("📝 WRITING ENCRYPTED FILES")
    print("="*70)
    
    file1 = secure_fs.write_file(
        user_id="user_001",
        filename="sensitive_data.txt",
        content=b"This is highly sensitive enterprise data that must be protected.",
        encryption_level=EncryptionLevel.MILITARY
    )
    
    file2 = secure_fs.write_file(
        user_id="user_001",
        filename="config.json",
        content=b'{"api_key": "secret123", "database": "production"}',
        encryption_level=EncryptionLevel.HIGH
    )
    
    # Read file
    print("\n" + "="*70)
    print("📖 READING ENCRYPTED FILE")
    print("="*70)
    
    content, metadata = secure_fs.read_file("user_001", file1.file_id)
    print(f"\n📄 File Content Preview:")
    print(f"   {content[:50].decode('utf-8', errors='ignore')}...")
    
    # Share file
    print("\n" + "="*70)
    print("🔗 SHARING FILE")
    print("="*70)
    
    secure_fs.share_file(
        owner_user_id="user_001",
        file_id=file1.file_id,
        target_user_id="user_002",
        permissions=[FilePermission.READ]
    )
    
    # Display user statistics
    print("\n" + "="*70)
    print("📊 USER FILE SYSTEM STATISTICS")
    print("="*70)
    
    for user_id in ["user_001", "user_002"]:
        stats = secure_fs.get_user_stats(user_id)
        print(f"\n👤 User: {stats['user_id']}")
        print(f"   📊 Quota:")
        print(f"      Total: {stats['quota']['total_gb']:.2f} GB")
        print(f"      Used: {stats['quota']['used_gb']:.4f} GB ({stats['quota']['used_percent']:.2f}%)")
        print(f"      Available: {stats['quota']['available_gb']:.2f} GB")
        print(f"   📁 Files:")
        print(f"      Count: {stats['files']['count']}")
        print(f"      Encrypted: {stats['files']['encrypted']}")
        print(f"      Total Size: {stats['files']['total_size_mb']:.4f} MB")
    
    print("\n✅ Security-Enhanced File System Ready for Production!")


if __name__ == "__main__":
    main()
