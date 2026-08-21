#!/usr/bin/env python3
"""
ArciTEK.AI Deployment Automation
Deploy to Cloudflare Workers, AWS, GCP, or Azure
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Color codes
class Colors:
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'


class DeploymentManager:
    """Manages ArciTEK.AI deployments"""
    
    SUPPORTED_TARGETS = ['cloudflare', 'aws', 'gcp', 'azure', 'docker']
    
    def __init__(self, target: str, environment: str = 'production'):
        self.target = target
        self.environment = environment
        self.root_dir = Path(__file__).parent.parent
        self.config_dir = self.root_dir / "config"
        
        if target not in self.SUPPORTED_TARGETS:
            raise ValueError(f"Unsupported deployment target: {target}")
    
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
    
    def run_command(self, command: List[str], cwd: Optional[Path] = None) -> bool:
        """Run a shell command"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.root_dir,
                check=True,
                capture_output=True,
                text=True
            )
            return True
        except subprocess.CalledProcessError as e:
            self.print_error(f"Command failed: {' '.join(command)}")
            self.print_error(f"Error: {e.stderr}")
            return False
    
    def check_prerequisites(self) -> bool:
        """Check deployment prerequisites"""
        self.print_info("Checking prerequisites...")
        
        prerequisites = {
            'cloudflare': ['wrangler'],
            'aws': ['aws'],
            'gcp': ['gcloud'],
            'azure': ['az'],
            'docker': ['docker']
        }
        
        required_tools = prerequisites.get(self.target, [])
        
        for tool in required_tools:
            if not self._check_command_exists(tool):
                self.print_error(f"Required tool not found: {tool}")
                return False
        
        self.print_success("All prerequisites met")
        return True
    
    def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists"""
        try:
            subprocess.run(
                ['which', command],
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
    
    def build_project(self) -> bool:
        """Build the project"""
        self.print_info("Building project...")
        
        # Install dependencies
        if not self.run_command(['pip3', 'install', '-q', '-r', 'requirements.txt']):
            return False
        
        if (self.root_dir / 'package.json').exists():
            if not self.run_command(['npm', 'install', '--silent']):
                return False
            
            # Build frontend if needed
            if not self.run_command(['npm', 'run', 'build']):
                self.print_warning("Frontend build failed or not configured")
        
        self.print_success("Project built successfully")
        return True
    
    def run_tests(self) -> bool:
        """Run tests before deployment"""
        self.print_info("Running tests...")
        
        try:
            result = subprocess.run(
                ['python3', '-m', 'pytest', 'tests/', '-v'],
                cwd=self.root_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.print_success("All tests passed")
                return True
            else:
                self.print_warning("Some tests failed")
                print(result.stdout)
                
                # Ask if user wants to continue
                response = input(f"{Colors.YELLOW}Continue deployment anyway? (y/N): {Colors.NC}")
                return response.lower() in ['y', 'yes']
                
        except Exception as e:
            self.print_warning(f"Could not run tests: {e}")
            return True  # Continue anyway
    
    def deploy_to_cloudflare(self) -> bool:
        """Deploy to Cloudflare Workers"""
        self.print_info("Deploying to Cloudflare Workers...")
        
        # Check for wrangler.toml
        wrangler_config = self.root_dir / 'wrangler.toml'
        if not wrangler_config.exists():
            self.print_info("Creating wrangler.toml...")
            self._create_wrangler_config()
        
        # Deploy using wrangler
        env_flag = f"--env {self.environment}" if self.environment != 'production' else ""
        command = f"wrangler deploy {env_flag}".split()
        
        if self.run_command(command):
            self.print_success("Deployed to Cloudflare Workers")
            self.print_info("URL: https://infinite2025.com")
            return True
        else:
            return False
    
    def _create_wrangler_config(self):
        """Create wrangler.toml configuration"""
        config = """name = "arcitek-ai"
main = "arcitek_core/main.py"
compatibility_date = "2024-01-01"

[env.production]
name = "arcitek-ai-production"
route = "infinite2025.com/*"

[env.staging]
name = "arcitek-ai-staging"
route = "staging.infinite2025.com/*"

[[kv_namespaces]]
binding = "ARCITEK_KV"
id = "your_kv_namespace_id"

[[r2_buckets]]
binding = "ARCITEK_STORAGE"
bucket_name = "arcitek-storage"

[vars]
ENVIRONMENT = "production"
"""
        
        (self.root_dir / 'wrangler.toml').write_text(config)
    
    def deploy_to_aws(self) -> bool:
        """Deploy to AWS"""
        self.print_info("Deploying to AWS...")
        
        # Use AWS SAM or CDK for deployment
        self.print_warning("AWS deployment requires manual configuration")
        self.print_info("Please configure AWS SAM or CDK templates")
        
        return False
    
    def deploy_to_gcp(self) -> bool:
        """Deploy to Google Cloud Platform"""
        self.print_info("Deploying to GCP...")
        
        # Use gcloud for deployment
        self.print_warning("GCP deployment requires manual configuration")
        self.print_info("Please configure Google Cloud Run or App Engine")
        
        return False
    
    def deploy_to_azure(self) -> bool:
        """Deploy to Azure"""
        self.print_info("Deploying to Azure...")
        
        # Use Azure CLI for deployment
        self.print_warning("Azure deployment requires manual configuration")
        self.print_info("Please configure Azure App Service or Container Instances")
        
        return False
    
    def deploy_to_docker(self) -> bool:
        """Build and push Docker image"""
        self.print_info("Building Docker image...")
        
        # Check for Dockerfile
        dockerfile = self.root_dir / 'Dockerfile'
        if not dockerfile.exists():
            self.print_info("Creating Dockerfile...")
            self._create_dockerfile()
        
        # Build image
        image_tag = f"arcitek-ai:{self.environment}"
        
        if not self.run_command(['docker', 'build', '-t', image_tag, '.']):
            return False
        
        self.print_success(f"Docker image built: {image_tag}")
        
        # Ask if user wants to push
        response = input(f"{Colors.YELLOW}Push to Docker registry? (y/N): {Colors.NC}")
        if response.lower() in ['y', 'yes']:
            registry = input(f"{Colors.YELLOW}Docker registry URL: {Colors.NC}")
            if registry:
                full_tag = f"{registry}/{image_tag}"
                self.run_command(['docker', 'tag', image_tag, full_tag])
                self.run_command(['docker', 'push', full_tag])
        
        return True
    
    def _create_dockerfile(self):
        """Create Dockerfile"""
        dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    build-essential \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \\
    && apt-get install -y nodejs

# Copy requirements
COPY requirements.txt package.json ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies
RUN npm install --production

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python3", "arcitek_core/main.py"]
"""
        
        (self.root_dir / 'Dockerfile').write_text(dockerfile_content)
    
    def deploy(self) -> bool:
        """Main deployment process"""
        self.print_header(f"ArciTEK.AI Deployment - {self.target.upper()}")
        
        self.print_info(f"Environment: {self.environment}")
        self.print_info(f"Target: {self.target}")
        print()
        
        # Check prerequisites
        if not self.check_prerequisites():
            return False
        
        # Build project
        if not self.build_project():
            return False
        
        # Run tests
        if not self.run_tests():
            return False
        
        # Deploy to target
        deployment_methods = {
            'cloudflare': self.deploy_to_cloudflare,
            'aws': self.deploy_to_aws,
            'gcp': self.deploy_to_gcp,
            'azure': self.deploy_to_azure,
            'docker': self.deploy_to_docker
        }
        
        deploy_method = deployment_methods[self.target]
        
        if deploy_method():
            print()
            self.print_success("Deployment completed successfully!")
            print()
            return True
        else:
            print()
            self.print_error("Deployment failed")
            print()
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Deploy ArciTEK.AI to various platforms'
    )
    
    parser.add_argument(
        'target',
        choices=DeploymentManager.SUPPORTED_TARGETS,
        help='Deployment target'
    )
    
    parser.add_argument(
        '--environment',
        '-e',
        choices=['production', 'staging', 'development'],
        default='production',
        help='Deployment environment (default: production)'
    )
    
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip running tests before deployment'
    )
    
    args = parser.parse_args()
    
    try:
        manager = DeploymentManager(args.target, args.environment)
        
        if args.skip_tests:
            manager.run_tests = lambda: True
        
        success = manager.deploy()
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Deployment cancelled{Colors.NC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.NC}")
        sys.exit(1)


if __name__ == "__main__":
    main()
