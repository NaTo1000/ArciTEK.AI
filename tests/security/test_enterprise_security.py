#!/usr/bin/env python3
"""
Test Suite for ArciTEK.AI Enterprise Security Platform
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import unittest
from datetime import datetime
from arcitek_core.secure_auth import (
    SecureAuthenticationManager, AuthMethod, AccessLevel,
    UserAccount, AuthSession
)
from arcitek_core.secure_filesystem import (
    SecureFileSystem, FilePermission, EncryptionLevel
)
from arcitek_core.gcp_cluster_deploy import (
    GoogleCloudClusterManager, ClusterType, NodeType
)


class TestSecureAuthentication(unittest.TestCase):
    """Test secure authentication features"""
    
    def setUp(self):
        """Set up test environment"""
        self.auth_manager = SecureAuthenticationManager()
    
    def test_create_user_ssh_key(self):
        """Test user creation with SSH key authentication"""
        user = self.auth_manager.create_user_account(
            username="test_ssh_user",
            email="test@example.com",
            auth_method=AuthMethod.SSH_KEY,
            access_level=AccessLevel.READ_WRITE,
            security_clearance=3
        )
        
        self.assertIsInstance(user, UserAccount)
        self.assertEqual(user.username, "test_ssh_user")
        self.assertEqual(user.auth_method, AuthMethod.SSH_KEY)
        self.assertIsNotNone(user.ssh_public_key)
        self.assertTrue(user.active)
    
    def test_create_user_sha512_key(self):
        """Test user creation with SHA512 key authentication"""
        user = self.auth_manager.create_user_account(
            username="test_sha512_user",
            email="test@example.com",
            auth_method=AuthMethod.SHA512_KEY,
            access_level=AccessLevel.READ_ONLY,
            security_clearance=2
        )
        
        self.assertIsInstance(user, UserAccount)
        self.assertEqual(user.username, "test_sha512_user")
        self.assertEqual(user.auth_method, AuthMethod.SHA512_KEY)
        self.assertIsNotNone(user.sha512_key_hash)
        self.assertTrue(user.active)
    
    def test_create_user_combined_auth(self):
        """Test user creation with combined authentication"""
        user = self.auth_manager.create_user_account(
            username="test_combined_user",
            email="test@example.com",
            auth_method=AuthMethod.COMBINED,
            access_level=AccessLevel.SUPER_ADMIN,
            security_clearance=5
        )
        
        self.assertIsInstance(user, UserAccount)
        self.assertEqual(user.auth_method, AuthMethod.COMBINED)
        self.assertIsNotNone(user.ssh_public_key)
        self.assertIsNotNone(user.sha512_key_hash)
    
    def test_ssh_key_generation(self):
        """Test SSH key pair generation"""
        private_key, public_key = self.auth_manager.generate_ssh_key_pair()
        
        self.assertIsInstance(private_key, str)
        self.assertIsInstance(public_key, str)
        self.assertIn("BEGIN PRIVATE KEY", private_key)
        self.assertIn("ssh-rsa", public_key)
    
    def test_sha512_key_generation(self):
        """Test SHA512 key generation"""
        key_encoded, key_hash = self.auth_manager.generate_sha512_key("testuser")
        
        self.assertIsInstance(key_encoded, str)
        self.assertIsInstance(key_hash, str)
        self.assertEqual(len(key_hash), 128)  # SHA512 produces 128 hex characters
    
    def test_session_validation(self):
        """Test session creation and validation"""
        user = self.auth_manager.create_user_account(
            username="session_test_user",
            email="test@example.com",
            auth_method=AuthMethod.SSH_KEY,
            access_level=AccessLevel.READ_WRITE
        )
        
        session = self.auth_manager._create_session(user, AuthMethod.SSH_KEY, "127.0.0.1")
        
        self.assertIsInstance(session, AuthSession)
        self.assertTrue(self.auth_manager.validate_session(session.session_id))
    
    def test_security_summary(self):
        """Test security summary generation"""
        summary = self.auth_manager.get_security_summary()
        
        self.assertIn("total_users", summary)
        self.assertIn("active_sessions", summary)
        self.assertIn("auth_methods", summary)
        self.assertIsInstance(summary["total_users"], int)


class TestSecureFileSystem(unittest.TestCase):
    """Test secure file system features"""
    
    def setUp(self):
        """Set up test environment"""
        self.file_system = SecureFileSystem()
        self.test_user_id = "test_user_001"
        self.file_system.create_user_filesystem(self.test_user_id, quota_gb=10)
    
    def test_create_user_filesystem(self):
        """Test user filesystem creation"""
        new_user_id = "test_user_002"
        fs_path = self.file_system.create_user_filesystem(new_user_id, quota_gb=50)
        
        self.assertIn(new_user_id, self.file_system.user_quotas)
        self.assertEqual(self.file_system.user_quotas[new_user_id].total_bytes, 50 * 1024**3)
        self.assertTrue(os.path.exists(fs_path))
    
    def test_write_file_standard_encryption(self):
        """Test writing file with standard encryption"""
        content = b"Test content for standard encryption"
        
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="test_standard.txt",
            content=content,
            encryption_level=EncryptionLevel.STANDARD
        )
        
        self.assertEqual(metadata.filename, "test_standard.txt")
        self.assertTrue(metadata.encrypted)
        self.assertEqual(metadata.encryption_level, EncryptionLevel.STANDARD)
        self.assertEqual(metadata.size_bytes, len(content))
    
    def test_write_file_high_encryption(self):
        """Test writing file with high encryption"""
        content = b"Test content for high encryption"
        
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="test_high.txt",
            content=content,
            encryption_level=EncryptionLevel.HIGH
        )
        
        self.assertTrue(metadata.encrypted)
        self.assertEqual(metadata.encryption_level, EncryptionLevel.HIGH)
    
    def test_write_file_military_encryption(self):
        """Test writing file with military encryption"""
        content = b"Test content for military encryption"
        
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="test_military.txt",
            content=content,
            encryption_level=EncryptionLevel.MILITARY
        )
        
        self.assertTrue(metadata.encrypted)
        self.assertEqual(metadata.encryption_level, EncryptionLevel.MILITARY)
    
    def test_read_encrypted_file(self):
        """Test reading encrypted file"""
        original_content = b"Secret data that must be protected"
        
        # Write file
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="secret.txt",
            content=original_content,
            encryption_level=EncryptionLevel.HIGH
        )
        
        # Read file
        read_content, read_metadata = self.file_system.read_file(
            user_id=self.test_user_id,
            file_id=metadata.file_id
        )
        
        self.assertEqual(read_content, original_content)
        self.assertEqual(read_metadata.file_id, metadata.file_id)
    
    def test_file_permissions(self):
        """Test file permission system"""
        content = b"Test content for permissions"
        
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="permission_test.txt",
            content=content,
            encryption_level=EncryptionLevel.STANDARD
        )
        
        # Owner should have all permissions
        self.assertTrue(
            self.file_system._check_permission(
                self.test_user_id, 
                metadata.file_id, 
                FilePermission.READ
            )
        )
        self.assertTrue(
            self.file_system._check_permission(
                self.test_user_id, 
                metadata.file_id, 
                FilePermission.WRITE
            )
        )
    
    def test_file_sharing(self):
        """Test file sharing functionality"""
        content = b"Shared content"
        target_user = "test_user_002"
        self.file_system.create_user_filesystem(target_user, quota_gb=10)
        
        # Write file
        metadata = self.file_system.write_file(
            user_id=self.test_user_id,
            filename="shared.txt",
            content=content,
            encryption_level=EncryptionLevel.STANDARD
        )
        
        # Share file
        self.file_system.share_file(
            owner_user_id=self.test_user_id,
            file_id=metadata.file_id,
            target_user_id=target_user,
            permissions=[FilePermission.READ]
        )
        
        # Target user should have read permission
        self.assertTrue(
            self.file_system._check_permission(
                target_user, 
                metadata.file_id, 
                FilePermission.READ
            )
        )
    
    def test_quota_management(self):
        """Test quota management"""
        quota = self.file_system.user_quotas[self.test_user_id]
        initial_used = quota.used_bytes
        
        content = b"x" * 1024  # 1KB content
        
        self.file_system.write_file(
            user_id=self.test_user_id,
            filename="quota_test.txt",
            content=content,
            encryption_level=EncryptionLevel.NONE
        )
        
        # Quota should be updated
        self.assertEqual(quota.used_bytes, initial_used + len(content))
        self.assertEqual(quota.file_count, 1)
    
    def test_user_stats(self):
        """Test user statistics"""
        stats = self.file_system.get_user_stats(self.test_user_id)
        
        self.assertIn("user_id", stats)
        self.assertIn("quota", stats)
        self.assertIn("files", stats)
        self.assertEqual(stats["user_id"], self.test_user_id)


class TestGoogleCloudDeployment(unittest.TestCase):
    """Test Google Cloud deployment features"""
    
    def setUp(self):
        """Set up test environment"""
        self.cluster_manager = GoogleCloudClusterManager(
            project_id="test-project",
            credentials_path=None
        )
    
    def test_create_cluster(self):
        """Test cluster creation"""
        cluster = self.cluster_manager.create_cluster(
            cluster_name="test-cluster",
            cluster_type=ClusterType.DEVELOPMENT,
            region="us-central1",
            min_nodes=2,
            max_nodes=5
        )
        
        self.assertEqual(cluster.cluster_name, "test-cluster")
        self.assertEqual(cluster.cluster_type, ClusterType.DEVELOPMENT)
        self.assertEqual(cluster.region, "us-central1")
        self.assertTrue(cluster.auto_scaling)
    
    def test_add_node_pool(self):
        """Test adding node pool"""
        # First create cluster
        self.cluster_manager.create_cluster(
            cluster_name="test-cluster-2",
            cluster_type=ClusterType.PRODUCTION,
            region="us-east1"
        )
        
        # Add node pool
        node_pool = self.cluster_manager.add_node_pool(
            cluster_name="test-cluster-2",
            pool_name="high-cpu-pool",
            node_type=NodeType.HIGH_CPU,
            node_count=3
        )
        
        self.assertEqual(node_pool.name, "high-cpu-pool")
        self.assertEqual(node_pool.node_type, NodeType.HIGH_CPU)
        self.assertEqual(node_pool.node_count, 3)
    
    def test_create_load_balancer(self):
        """Test load balancer creation"""
        self.cluster_manager.create_cluster(
            cluster_name="test-cluster-3",
            cluster_type=ClusterType.PRODUCTION
        )
        
        lb = self.cluster_manager.create_load_balancer(
            cluster_name="test-cluster-3",
            lb_name="test-lb",
            ssl_enabled=True
        )
        
        self.assertEqual(lb.name, "test-lb")
        self.assertTrue(lb.ssl_enabled)
        self.assertEqual(lb.frontend_config["protocol"], "HTTPS")
    
    def test_kubernetes_deployment_generation(self):
        """Test Kubernetes deployment YAML generation"""
        yaml_content = self.cluster_manager.generate_kubernetes_deployment(
            app_name="test-app",
            image="gcr.io/test/app:latest",
            replicas=3,
            port=8080
        )
        
        self.assertIsInstance(yaml_content, str)
        self.assertIn("kind: Deployment", yaml_content)
        self.assertIn("kind: Service", yaml_content)
        self.assertIn("kind: HorizontalPodAutoscaler", yaml_content)
        self.assertIn("test-app", yaml_content)
    
    def test_terraform_config_generation(self):
        """Test Terraform configuration generation"""
        self.cluster_manager.create_cluster(
            cluster_name="test-cluster-4",
            cluster_type=ClusterType.PRODUCTION
        )
        
        terraform_config = self.cluster_manager.generate_terraform_config("test-cluster-4")
        
        self.assertIsInstance(terraform_config, str)
        self.assertIn("terraform", terraform_config)
        self.assertIn("google_container_cluster", terraform_config)
        self.assertIn("google_container_node_pool", terraform_config)
    
    def test_deployment_summary(self):
        """Test deployment summary"""
        summary = self.cluster_manager.get_deployment_summary()
        
        self.assertIn("total_clusters", summary)
        self.assertIn("project_id", summary)
        self.assertEqual(summary["project_id"], "test-project")


def run_tests():
    """Run all tests"""
    print("\n" + "="*70)
    print("🧪 ArciTEK.AI Enterprise Security Platform - Test Suite")
    print("="*70 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestSecureAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestSecureFileSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestGoogleCloudDeployment))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit(run_tests())
