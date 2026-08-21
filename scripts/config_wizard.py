#!/usr/bin/env python3
"""
ArciTEK.AI Configuration Wizard
Interactive setup for API keys, quantum platforms, and AI models
"""

import os
import sys
import json
import getpass
from pathlib import Path
from typing import Dict, Optional

# Color codes
class Colors:
    CYAN = '\033[0;36m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    NC = '\033[0m'  # No Color


class ConfigWizard:
    """Interactive configuration wizard for ArciTEK.AI"""
    
    def __init__(self):
        self.config_dir = Path(__file__).parent.parent / "config"
        self.config_dir.mkdir(exist_ok=True)
        self.env_file = self.config_dir / ".env"
        self.config_file = self.config_dir / "config.json"
        self.config = {}
        
    def print_header(self, text: str):
        """Print section header"""
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.CYAN}{text.center(60)}{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}\n")
    
    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ{Colors.NC}  {text}")
    
    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}✓{Colors.NC}  {text}")
    
    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}!{Colors.NC}  {text}")
    
    def ask_question(self, question: str, default: Optional[str] = None, 
                     secret: bool = False) -> str:
        """Ask a configuration question"""
        if default:
            prompt = f"{Colors.MAGENTA}?{Colors.NC} {question} [{default}]: "
        else:
            prompt = f"{Colors.MAGENTA}?{Colors.NC} {question}: "
        
        if secret:
            answer = getpass.getpass(prompt)
        else:
            answer = input(prompt)
        
        return answer.strip() or default or ""
    
    def ask_yes_no(self, question: str, default: bool = True) -> bool:
        """Ask yes/no question"""
        default_str = "Y/n" if default else "y/N"
        answer = self.ask_question(f"{question} ({default_str})", 
                                   "y" if default else "n")
        return answer.lower() in ['y', 'yes', '1', 'true']
    
    def configure_quantum_platforms(self):
        """Configure quantum computing platforms"""
        self.print_header("Quantum Computing Platforms")
        
        self.print_info("ArciTEK.AI supports 5 quantum platforms:")
        print("  1. IBM Quantum (Qiskit)")
        print("  2. IonQ")
        print("  3. Google Quantum AI (Cirq)")
        print("  4. Amazon Braket")
        print("  5. Azure Quantum")
        print()
        
        quantum_config = {}
        
        # IBM Quantum
        if self.ask_yes_no("Configure IBM Quantum?", True):
            self.print_info("Get your API token from: https://quantum-computing.ibm.com/")
            token = self.ask_question("IBM Quantum API Token", secret=True)
            if token:
                quantum_config['IBM_QUANTUM_TOKEN'] = token
                self.print_success("IBM Quantum configured")
        
        # IonQ
        if self.ask_yes_no("Configure IonQ?", False):
            self.print_info("Get your API key from: https://cloud.ionq.com/")
            key = self.ask_question("IonQ API Key", secret=True)
            if key:
                quantum_config['IONQ_API_KEY'] = key
                self.print_success("IonQ configured")
        
        # Google Quantum AI
        if self.ask_yes_no("Configure Google Quantum AI?", False):
            self.print_info("Requires Google Cloud credentials")
            project = self.ask_question("Google Cloud Project ID")
            if project:
                quantum_config['GOOGLE_QUANTUM_PROJECT'] = project
                self.print_success("Google Quantum AI configured")
        
        # Amazon Braket
        if self.ask_yes_no("Configure Amazon Braket?", False):
            self.print_info("Requires AWS credentials")
            access_key = self.ask_question("AWS Access Key ID", secret=True)
            secret_key = self.ask_question("AWS Secret Access Key", secret=True)
            region = self.ask_question("AWS Region", "us-east-1")
            if access_key and secret_key:
                quantum_config['AWS_ACCESS_KEY_ID'] = access_key
                quantum_config['AWS_SECRET_ACCESS_KEY'] = secret_key
                quantum_config['AWS_REGION'] = region
                self.print_success("Amazon Braket configured")
        
        # Azure Quantum
        if self.ask_yes_no("Configure Azure Quantum?", False):
            self.print_info("Requires Azure subscription")
            subscription = self.ask_question("Azure Subscription ID")
            resource_group = self.ask_question("Resource Group")
            workspace = self.ask_question("Workspace Name")
            if subscription and resource_group and workspace:
                quantum_config['AZURE_SUBSCRIPTION_ID'] = subscription
                quantum_config['AZURE_RESOURCE_GROUP'] = resource_group
                quantum_config['AZURE_QUANTUM_WORKSPACE'] = workspace
                self.print_success("Azure Quantum configured")
        
        self.config['quantum'] = quantum_config
    
    def configure_ai_models(self):
        """Configure AI model integrations"""
        self.print_header("AI Model Integrations")
        
        self.print_info("ArciTEK.AI integrates with multiple AI platforms:")
        print("  • OpenAI (GPT-4, GPT-3.5)")
        print("  • Anthropic (Claude)")
        print("  • Google (Gemini)")
        print("  • IBM WatsonX")
        print("  • Hugging Face")
        print()
        
        ai_config = {}
        
        # OpenAI
        if self.ask_yes_no("Configure OpenAI?", True):
            self.print_info("Get your API key from: https://platform.openai.com/")
            key = self.ask_question("OpenAI API Key", secret=True)
            if key:
                ai_config['OPENAI_API_KEY'] = key
                self.print_success("OpenAI configured")
        
        # Anthropic
        if self.ask_yes_no("Configure Anthropic Claude?", False):
            self.print_info("Get your API key from: https://console.anthropic.com/")
            key = self.ask_question("Anthropic API Key", secret=True)
            if key:
                ai_config['ANTHROPIC_API_KEY'] = key
                self.print_success("Anthropic configured")
        
        # Google Gemini
        if self.ask_yes_no("Configure Google Gemini?", False):
            self.print_info("Get your API key from: https://makersuite.google.com/")
            key = self.ask_question("Google AI API Key", secret=True)
            if key:
                ai_config['GOOGLE_AI_API_KEY'] = key
                self.print_success("Google Gemini configured")
        
        # IBM WatsonX
        if self.ask_yes_no("Configure IBM WatsonX?", False):
            self.print_info("Get your API key from: https://cloud.ibm.com/")
            key = self.ask_question("IBM Cloud API Key", secret=True)
            project_id = self.ask_question("WatsonX Project ID")
            if key and project_id:
                ai_config['IBM_CLOUD_API_KEY'] = key
                ai_config['WATSONX_PROJECT_ID'] = project_id
                self.print_success("IBM WatsonX configured")
        
        # Hugging Face
        if self.ask_yes_no("Configure Hugging Face?", False):
            self.print_info("Get your token from: https://huggingface.co/settings/tokens")
            token = self.ask_question("Hugging Face Token", secret=True)
            if token:
                ai_config['HUGGINGFACE_TOKEN'] = token
                self.print_success("Hugging Face configured")
        
        self.config['ai_models'] = ai_config
    
    def configure_database(self):
        """Configure database settings"""
        self.print_header("Database Configuration")
        
        db_type = self.ask_question("Database type (postgresql/mongodb/sqlite)", "postgresql")
        
        db_config = {'type': db_type}
        
        if db_type in ['postgresql', 'mongodb']:
            db_config['host'] = self.ask_question("Database host", "localhost")
            db_config['port'] = self.ask_question("Database port", 
                                                  "5432" if db_type == "postgresql" else "27017")
            db_config['database'] = self.ask_question("Database name", "arcitek_ai")
            db_config['username'] = self.ask_question("Database username")
            db_config['password'] = self.ask_question("Database password", secret=True)
        else:
            db_config['path'] = self.ask_question("SQLite database path", 
                                                  "./data/arcitek.db")
        
        self.config['database'] = db_config
        self.print_success("Database configured")
    
    def configure_general_settings(self):
        """Configure general platform settings"""
        self.print_header("General Settings")
        
        general_config = {}
        
        general_config['environment'] = self.ask_question(
            "Environment (development/production)", "development")
        
        general_config['host'] = self.ask_question("Server host", "0.0.0.0")
        general_config['port'] = self.ask_question("Server port", "8000")
        
        general_config['log_level'] = self.ask_question(
            "Log level (DEBUG/INFO/WARNING/ERROR)", "INFO")
        
        # Precision build settings
        self.print_info("Precision Build System Settings")
        general_config['precision_target'] = self.ask_question(
            "Target precision (%)", "99.97")
        
        general_config['enable_quantum_boost'] = self.ask_yes_no(
            "Enable quantum performance boost?", True)
        
        general_config['enable_naydoev1'] = self.ask_yes_no(
            "Enable NayDoeV1 learning environments?", True)
        
        self.config['general'] = general_config
        self.print_success("General settings configured")
    
    def save_configuration(self):
        """Save configuration to files"""
        self.print_header("Saving Configuration")
        
        # Save to .env file
        with open(self.env_file, 'w') as f:
            f.write("# ArciTEK.AI Configuration\n")
            f.write("# Generated by Configuration Wizard\n\n")
            
            # General settings
            if 'general' in self.config:
                f.write("# General Settings\n")
                for key, value in self.config['general'].items():
                    env_key = f"ARCITEK_{key.upper()}"
                    f.write(f"{env_key}={value}\n")
                f.write("\n")
            
            # Quantum platforms
            if 'quantum' in self.config:
                f.write("# Quantum Computing Platforms\n")
                for key, value in self.config['quantum'].items():
                    f.write(f"{key}={value}\n")
                f.write("\n")
            
            # AI models
            if 'ai_models' in self.config:
                f.write("# AI Model Integrations\n")
                for key, value in self.config['ai_models'].items():
                    f.write(f"{key}={value}\n")
                f.write("\n")
            
            # Database
            if 'database' in self.config:
                f.write("# Database Configuration\n")
                db = self.config['database']
                if db['type'] in ['postgresql', 'mongodb']:
                    db_url = f"{db['type']}://{db['username']}:{db['password']}@{db['host']}:{db['port']}/{db['database']}"
                    f.write(f"DATABASE_URL={db_url}\n")
                else:
                    f.write(f"DATABASE_URL=sqlite:///{db['path']}\n")
                f.write("\n")
        
        self.print_success(f"Configuration saved to {self.env_file}")
        
        # Save to JSON config file
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
        
        self.print_success(f"Configuration saved to {self.config_file}")
    
    def run(self):
        """Run the configuration wizard"""
        print(f"\n{Colors.CYAN}")
        print("╔═══════════════════════════════════════════════════════════╗")
        print("║     ArciTEK.AI Configuration Wizard                       ║")
        print("║     infinite♾2025                                         ║")
        print("╚═══════════════════════════════════════════════════════════╝")
        print(f"{Colors.NC}\n")
        
        self.print_info("This wizard will help you configure ArciTEK.AI")
        self.print_info("You can skip any section and configure it later")
        print()
        
        try:
            # Run configuration sections
            self.configure_general_settings()
            self.configure_quantum_platforms()
            self.configure_ai_models()
            self.configure_database()
            
            # Save configuration
            self.save_configuration()
            
            print()
            self.print_success("Configuration completed successfully!")
            print()
            self.print_info("You can now start ArciTEK.AI with: ./startup.sh start")
            self.print_info("To reconfigure: ./startup.sh config")
            print()
            
            return 0
            
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Configuration cancelled{Colors.NC}")
            return 1
        except Exception as e:
            print(f"\n{Colors.RED}Error: {e}{Colors.NC}")
            return 1


def main():
    """Main entry point"""
    wizard = ConfigWizard()
    sys.exit(wizard.run())


if __name__ == "__main__":
    main()
