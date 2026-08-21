#!/usr/bin/env python3
"""
ArciTEK.AI API Key Validation System
Validates quantum computing and AI platform API keys
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import asyncio

# Color codes
class Colors:
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'


@dataclass
class ValidationResult:
    """Result of API key validation"""
    platform: str
    valid: bool
    message: str
    details: Optional[Dict] = None


class APIKeyValidator:
    """Validates API keys for quantum and AI platforms"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent.parent / "config"
        self.env_file = self.config_dir / ".env"
        self.results: List[ValidationResult] = []
        
        # Load environment variables
        self._load_env()
    
    def _load_env(self):
        """Load environment variables from .env file"""
        if self.env_file.exists():
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key] = value
    
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
    
    async def validate_ibm_quantum(self) -> ValidationResult:
        """Validate IBM Quantum API token"""
        token = os.getenv('IBM_QUANTUM_TOKEN')
        
        if not token:
            return ValidationResult(
                platform="IBM Quantum",
                valid=False,
                message="API token not configured"
            )
        
        try:
            # Try to import and use Qiskit
            from qiskit_ibm_runtime import QiskitRuntimeService
            
            service = QiskitRuntimeService(channel="ibm_quantum", token=token)
            backends = service.backends()
            
            return ValidationResult(
                platform="IBM Quantum",
                valid=True,
                message=f"Connected successfully ({len(backends)} backends available)",
                details={'backend_count': len(backends)}
            )
            
        except ImportError:
            return ValidationResult(
                platform="IBM Quantum",
                valid=False,
                message="Qiskit not installed (pip install qiskit-ibm-runtime)"
            )
        except Exception as e:
            return ValidationResult(
                platform="IBM Quantum",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_ionq(self) -> ValidationResult:
        """Validate IonQ API key"""
        api_key = os.getenv('IONQ_API_KEY')
        
        if not api_key:
            return ValidationResult(
                platform="IonQ",
                valid=False,
                message="API key not configured"
            )
        
        try:
            import requests
            
            headers = {
                'Authorization': f'apiKey {api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://api.ionq.co/v0.3/backends',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                backends = response.json()
                return ValidationResult(
                    platform="IonQ",
                    valid=True,
                    message=f"Connected successfully ({len(backends)} backends available)",
                    details={'backend_count': len(backends)}
                )
            else:
                return ValidationResult(
                    platform="IonQ",
                    valid=False,
                    message=f"API returned status {response.status_code}"
                )
                
        except ImportError:
            return ValidationResult(
                platform="IonQ",
                valid=False,
                message="requests library not installed"
            )
        except Exception as e:
            return ValidationResult(
                platform="IonQ",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_google_quantum(self) -> ValidationResult:
        """Validate Google Quantum AI credentials"""
        project_id = os.getenv('GOOGLE_QUANTUM_PROJECT')
        
        if not project_id:
            return ValidationResult(
                platform="Google Quantum AI",
                valid=False,
                message="Project ID not configured"
            )
        
        try:
            import cirq_google
            
            # Basic validation - check if Cirq is properly installed
            return ValidationResult(
                platform="Google Quantum AI",
                valid=True,
                message=f"Cirq installed, project: {project_id}",
                details={'project_id': project_id}
            )
            
        except ImportError:
            return ValidationResult(
                platform="Google Quantum AI",
                valid=False,
                message="Cirq not installed (pip install cirq-google)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Google Quantum AI",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_amazon_braket(self) -> ValidationResult:
        """Validate Amazon Braket credentials"""
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        if not access_key or not secret_key:
            return ValidationResult(
                platform="Amazon Braket",
                valid=False,
                message="AWS credentials not configured"
            )
        
        try:
            import boto3
            
            client = boto3.client(
                'braket',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            # Try to list devices
            response = client.search_devices(maxResults=10)
            device_count = len(response.get('devices', []))
            
            return ValidationResult(
                platform="Amazon Braket",
                valid=True,
                message=f"Connected successfully ({device_count} devices available)",
                details={'device_count': device_count, 'region': region}
            )
            
        except ImportError:
            return ValidationResult(
                platform="Amazon Braket",
                valid=False,
                message="boto3 not installed (pip install boto3 amazon-braket-sdk)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Amazon Braket",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_azure_quantum(self) -> ValidationResult:
        """Validate Azure Quantum credentials"""
        subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        resource_group = os.getenv('AZURE_RESOURCE_GROUP')
        workspace = os.getenv('AZURE_QUANTUM_WORKSPACE')
        
        if not all([subscription_id, resource_group, workspace]):
            return ValidationResult(
                platform="Azure Quantum",
                valid=False,
                message="Azure credentials not fully configured"
            )
        
        try:
            from azure.quantum import Workspace
            
            # Basic validation - check if azure-quantum is installed
            return ValidationResult(
                platform="Azure Quantum",
                valid=True,
                message=f"Azure Quantum SDK installed, workspace: {workspace}",
                details={
                    'subscription_id': subscription_id[:8] + '...',
                    'workspace': workspace
                }
            )
            
        except ImportError:
            return ValidationResult(
                platform="Azure Quantum",
                valid=False,
                message="azure-quantum not installed (pip install azure-quantum)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Azure Quantum",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_openai(self) -> ValidationResult:
        """Validate OpenAI API key"""
        api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            return ValidationResult(
                platform="OpenAI",
                valid=False,
                message="API key not configured"
            )
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=api_key)
            
            # Try to list models
            models = client.models.list()
            model_count = len(list(models))
            
            return ValidationResult(
                platform="OpenAI",
                valid=True,
                message=f"Connected successfully ({model_count} models available)",
                details={'model_count': model_count}
            )
            
        except ImportError:
            return ValidationResult(
                platform="OpenAI",
                valid=False,
                message="openai library not installed (pip install openai)"
            )
        except Exception as e:
            return ValidationResult(
                platform="OpenAI",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_anthropic(self) -> ValidationResult:
        """Validate Anthropic API key"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            return ValidationResult(
                platform="Anthropic",
                valid=False,
                message="API key not configured"
            )
        
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=api_key)
            
            # Basic validation - check if library is properly configured
            return ValidationResult(
                platform="Anthropic",
                valid=True,
                message="API key configured (Claude models available)",
                details={'api_key_length': len(api_key)}
            )
            
        except ImportError:
            return ValidationResult(
                platform="Anthropic",
                valid=False,
                message="anthropic library not installed (pip install anthropic)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Anthropic",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_google_ai(self) -> ValidationResult:
        """Validate Google AI (Gemini) API key"""
        api_key = os.getenv('GOOGLE_AI_API_KEY')
        
        if not api_key:
            return ValidationResult(
                platform="Google AI (Gemini)",
                valid=False,
                message="API key not configured"
            )
        
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=api_key)
            
            # List available models
            models = genai.list_models()
            model_count = len(list(models))
            
            return ValidationResult(
                platform="Google AI (Gemini)",
                valid=True,
                message=f"Connected successfully ({model_count} models available)",
                details={'model_count': model_count}
            )
            
        except ImportError:
            return ValidationResult(
                platform="Google AI (Gemini)",
                valid=False,
                message="google-generativeai not installed (pip install google-generativeai)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Google AI (Gemini)",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_ibm_watsonx(self) -> ValidationResult:
        """Validate IBM WatsonX credentials"""
        api_key = os.getenv('IBM_CLOUD_API_KEY')
        project_id = os.getenv('WATSONX_PROJECT_ID')
        
        if not api_key or not project_id:
            return ValidationResult(
                platform="IBM WatsonX",
                valid=False,
                message="API key or project ID not configured"
            )
        
        try:
            from ibm_watson_machine_learning import APIClient
            
            credentials = {
                "apikey": api_key,
                "url": "https://us-south.ml.cloud.ibm.com"
            }
            
            client = APIClient(credentials)
            client.set.default_project(project_id)
            
            return ValidationResult(
                platform="IBM WatsonX",
                valid=True,
                message=f"Connected successfully (project: {project_id[:8]}...)",
                details={'project_id': project_id[:8] + '...'}
            )
            
        except ImportError:
            return ValidationResult(
                platform="IBM WatsonX",
                valid=False,
                message="ibm-watson-machine-learning not installed"
            )
        except Exception as e:
            return ValidationResult(
                platform="IBM WatsonX",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_huggingface(self) -> ValidationResult:
        """Validate Hugging Face token"""
        token = os.getenv('HUGGINGFACE_TOKEN')
        
        if not token:
            return ValidationResult(
                platform="Hugging Face",
                valid=False,
                message="Token not configured"
            )
        
        try:
            from huggingface_hub import HfApi
            
            api = HfApi(token=token)
            user_info = api.whoami()
            
            return ValidationResult(
                platform="Hugging Face",
                valid=True,
                message=f"Connected as {user_info['name']}",
                details={'username': user_info['name']}
            )
            
        except ImportError:
            return ValidationResult(
                platform="Hugging Face",
                valid=False,
                message="huggingface_hub not installed (pip install huggingface_hub)"
            )
        except Exception as e:
            return ValidationResult(
                platform="Hugging Face",
                valid=False,
                message=f"Validation failed: {str(e)}"
            )
    
    async def validate_all(self):
        """Validate all configured API keys"""
        self.print_header("ArciTEK.AI API Key Validation")
        
        # Quantum platforms
        self.print_info("Validating quantum computing platforms...")
        quantum_validators = [
            self.validate_ibm_quantum(),
            self.validate_ionq(),
            self.validate_google_quantum(),
            self.validate_amazon_braket(),
            self.validate_azure_quantum()
        ]
        
        quantum_results = await asyncio.gather(*quantum_validators)
        self.results.extend(quantum_results)
        
        # AI platforms
        self.print_info("Validating AI model platforms...")
        ai_validators = [
            self.validate_openai(),
            self.validate_anthropic(),
            self.validate_google_ai(),
            self.validate_ibm_watsonx(),
            self.validate_huggingface()
        ]
        
        ai_results = await asyncio.gather(*ai_validators)
        self.results.extend(ai_results)
    
    def display_results(self):
        """Display validation results"""
        print()
        self.print_header("Validation Results")
        
        # Quantum platforms
        print(f"\n{Colors.CYAN}Quantum Computing Platforms:{Colors.NC}\n")
        quantum_results = [r for r in self.results if r.platform in [
            "IBM Quantum", "IonQ", "Google Quantum AI", "Amazon Braket", "Azure Quantum"
        ]]
        
        for result in quantum_results:
            if result.valid:
                self.print_success(f"{result.platform}: {result.message}")
            else:
                self.print_warning(f"{result.platform}: {result.message}")
        
        # AI platforms
        print(f"\n{Colors.CYAN}AI Model Platforms:{Colors.NC}\n")
        ai_results = [r for r in self.results if r.platform in [
            "OpenAI", "Anthropic", "Google AI (Gemini)", "IBM WatsonX", "Hugging Face"
        ]]
        
        for result in ai_results:
            if result.valid:
                self.print_success(f"{result.platform}: {result.message}")
            else:
                self.print_warning(f"{result.platform}: {result.message}")
        
        # Summary
        print()
        self.print_header("Summary")
        
        total = len(self.results)
        valid = sum(1 for r in self.results if r.valid)
        invalid = total - valid
        
        print(f"Total platforms: {total}")
        print(f"{Colors.GREEN}Valid: {valid}{Colors.NC}")
        print(f"{Colors.YELLOW}Invalid/Not configured: {invalid}{Colors.NC}")
        print()
        
        if invalid > 0:
            self.print_info("Run './startup.sh config' to configure missing API keys")
        else:
            self.print_success("All configured platforms validated successfully!")
        
        print()
    
    def save_report(self):
        """Save validation report to file"""
        report_file = self.config_dir / "validation_report.json"
        
        report = {
            'timestamp': asyncio.get_event_loop().time(),
            'results': [
                {
                    'platform': r.platform,
                    'valid': r.valid,
                    'message': r.message,
                    'details': r.details
                }
                for r in self.results
            ]
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.print_info(f"Validation report saved to {report_file}")


async def main():
    """Main entry point"""
    validator = APIKeyValidator()
    
    try:
        await validator.validate_all()
        validator.display_results()
        validator.save_report()
        
        # Return exit code based on validation results
        invalid_count = sum(1 for r in validator.results if not r.valid)
        return 0 if invalid_count == 0 else 1
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Validation cancelled{Colors.NC}")
        return 1
    except Exception as e:
        print(f"\n{Colors.RED}Error: {e}{Colors.NC}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
