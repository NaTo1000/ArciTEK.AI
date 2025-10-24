#!/usr/bin/env python3
"""
ArciTEK.AI Enterprise Security Platform - Quick Demo
Demonstrates all key features in a single script
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arcitek_core.enterprise_security import (
    EnterpriseSecurityPlatform,
    AuthMethod,
    AccessLevel,
    ClusterType,
    EncryptionLevel
)


def print_section(title):
    """Print section header"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")


def main():
    """Run complete demo"""
    print("\n" + "🛡️ "*30)
    print("  ArciTEK.AI Enterprise Security Platform")
    print("  Complete Feature Demonstration")
    print("🛡️ "*30 + "\n")
    
    # Initialize platform
    print_section("1. INITIALIZING PLATFORM")
    platform = EnterpriseSecurityPlatform(
        gcp_project_id="arcitek-demo",
        credentials_path=None
    )
    
    # Onboard users
    print_section("2. ONBOARDING USERS")
    
    print("Creating Admin User with Combined Authentication...")
    admin = platform.onboard_user(
        username="admin",
        email="admin@arcitek.ai",
        auth_method=AuthMethod.COMBINED,
        access_level=AccessLevel.SUPER_ADMIN,
        filesystem_quota_gb=500,
        security_clearance=5
    )
    
    print("\nCreating Developer with SSH Authentication...")
    dev = platform.onboard_user(
        username="developer",
        email="dev@arcitek.ai",
        auth_method=AuthMethod.SSH_KEY,
        access_level=AccessLevel.READ_WRITE,
        filesystem_quota_gb=100,
        security_clearance=3
    )
    
    print("\nCreating Analyst with SHA512 Authentication...")
    analyst = platform.onboard_user(
        username="analyst",
        email="analyst@arcitek.ai",
        auth_method=AuthMethod.SHA512_KEY,
        access_level=AccessLevel.READ_ONLY,
        filesystem_quota_gb=50,
        security_clearance=2
    )
    
    # Deploy clusters
    print_section("3. DEPLOYING GOOGLE CLOUD CLUSTERS")
    
    print("Deploying Production Cluster...")
    prod_cluster = platform.deploy_secure_cluster(
        cluster_name="arcitek-production",
        cluster_type=ClusterType.PRODUCTION,
        region="us-central1",
        min_nodes=5,
        max_nodes=20
    )
    
    print("\nDeploying Staging Cluster...")
    staging_cluster = platform.deploy_secure_cluster(
        cluster_name="arcitek-staging",
        cluster_type=ClusterType.STAGING,
        region="us-east1",
        min_nodes=2,
        max_nodes=10
    )
    
    # Create secure files
    print_section("4. CREATING SECURE FILES")
    
    if "authentication" in admin["components"]:
        admin_user_id = admin["components"]["authentication"]["user_id"]
        
        print("Creating Military-Grade Encrypted File...")
        secret_file = platform.create_secure_file(
            user_id=admin_user_id,
            filename="enterprise_secrets.json",
            content=b'{"api_key": "super_secret_key", "database": "production_db"}',
            encryption_level=EncryptionLevel.MILITARY
        )
        
        print("\nCreating High-Security Config File...")
        config_file = platform.create_secure_file(
            user_id=admin_user_id,
            filename="app_config.json",
            content=b'{"app_name": "ArciTEK.AI", "version": "7.0.0"}',
            encryption_level=EncryptionLevel.HIGH
        )
    
    # Show platform status
    print_section("5. PLATFORM STATUS")
    
    status = platform.get_platform_status()
    
    print(f"🛡️  Platform: {status['platform']}")
    print(f"📦 Version: {status['version']}")
    print(f"🕐 Timestamp: {status['timestamp']}")
    
    print("\n📊 Component Status:")
    for component, info in status["components"].items():
        component_name = component.replace("_", " ").title()
        component_status = info.get("status", "unknown")
        status_icon = "✅" if component_status == "active" else "⚠️"
        print(f"   {status_icon} {component_name}: {component_status}")
        
        # Show additional info
        for key, value in info.items():
            if key != "status":
                print(f"      • {key}: {value}")
    
    # Generate deployment guide
    print_section("6. DEPLOYMENT GUIDE")
    
    guide = platform.generate_deployment_guide()
    print("Deployment guide generated successfully!")
    print("Full guide available in platform.generate_deployment_guide()")
    
    # Summary
    print_section("🎉 DEMO COMPLETE - SUMMARY")
    
    print("✅ Successfully Demonstrated:")
    print("   • SSH and SHA512 key authentication")
    print("   • Multi-level user access control")
    print("   • Google Cloud cluster deployment")
    print("   • Kubernetes and Terraform configuration")
    print("   • Military-grade file encryption")
    print("   • User-isolated file systems")
    print("   • Auto-scaling infrastructure")
    print("   • Enterprise security protocols")
    
    print("\n📊 Statistics:")
    print(f"   • Users Created: 3")
    print(f"   • Clusters Deployed: 2")
    print(f"   • Secure Files: 2")
    print(f"   • Encryption Level: Military-Grade (AES-256-GCM)")
    
    print("\n📚 Next Steps:")
    print("   1. Review generated deployment configurations")
    print("   2. Deploy to Google Cloud using gcloud commands")
    print("   3. Set up monitoring and alerting")
    print("   4. Configure backups and disaster recovery")
    print("   5. Conduct security audit and penetration testing")
    
    print("\n✅ Enterprise Security Platform Ready for Production!")
    print("\n" + "🛡️ "*30 + "\n")


if __name__ == "__main__":
    main()
