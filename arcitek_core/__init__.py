"""
ArciTEK.AI Core Module
The Ultimate Quantum-Enhanced Precision Build System

This module contains the core functionality for ArciTEK.AI including:
- Quantum-enhanced AI orchestration
- Precision build system
- NayDoeV1 learning integration
- Multi-platform compatibility
- Enterprise security and authentication
- Cloud deployment management
- Secure file system
"""

__version__ = "7.0.0"
__author__ = "NaTo1000"
__description__ = "ArciTEK.AI - The Ultimate Quantum-Enhanced Precision Build System"

# Import security modules (always available)
from .secure_auth import SecureAuthenticationManager
from .secure_filesystem import SecureFileSystem
from .gcp_cluster_deploy import GoogleCloudClusterManager
from .enterprise_security import EnterpriseSecurityPlatform

# Try to import optional modules
try:
    from .quantum_orchestrator import QuantumOrchestrator
except ImportError:
    QuantumOrchestrator = None

try:
    from .ai_model_manager import AIModelManager
except ImportError:
    AIModelManager = None

try:
    from .precision_builder import PrecisionBuilder
except ImportError:
    PrecisionBuilder = None

try:
    from .naydoev1_interface import NayDoeV1Interface
except ImportError:
    NayDoeV1Interface = None

__all__ = [
    'SecureAuthenticationManager',
    'SecureFileSystem',
    'GoogleCloudClusterManager',
    'EnterpriseSecurityPlatform',
    'QuantumOrchestrator',
    'AIModelManager', 
    'PrecisionBuilder',
    'NayDoeV1Interface'
]

