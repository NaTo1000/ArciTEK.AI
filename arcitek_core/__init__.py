"""
ArciTEK.AI Core Module
The Ultimate Quantum-Enhanced Precision Build System

This module contains the core functionality for ArciTEK.AI including:
- Quantum-enhanced AI orchestration
- Precision build system
- NayDoeV1 learning integration
- Multi-platform compatibility
"""

__version__ = "7.0.0"
__author__ = "NaTo1000"
__description__ = "ArciTEK.AI - The Ultimate Quantum-Enhanced Precision Build System"

try:
    from .quantum_orchestrator import QuantumOrchestrator
except ImportError:  # pragma: no cover - optional integration module
    QuantumOrchestrator = None

try:
    from .ai_model_manager import AIModelManager
except ImportError:  # pragma: no cover - optional integration module
    AIModelManager = None

try:
    from .naydoev1_interface import NayDoeV1Interface
except ImportError:  # pragma: no cover - optional integration module
    NayDoeV1Interface = None

from .precision_builder import ArciTEKPrecisionBuildSystem

PrecisionBuilder = ArciTEKPrecisionBuildSystem

__all__ = [
    'QuantumOrchestrator',
    'AIModelManager',
    'PrecisionBuilder',
    'ArciTEKPrecisionBuildSystem',
    'NayDoeV1Interface',
]

