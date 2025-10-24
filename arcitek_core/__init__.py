"""
ArciTEK.AI Core Module
The Ultimate Quantum-Enhanced Precision Build System

This module contains the core functionality for ArciTEK.AI including:
- Quantum-enhanced AI orchestration
- Precision build system
- NayDoeV1 learning integration
- Multi-platform compatibility
- Optimization engine and monitoring agents
"""

__version__ = "7.0.0"
__author__ = "NaTo1000"
__description__ = "ArciTEK.AI - The Ultimate Quantum-Enhanced Precision Build System"

# Import only modules that exist
try:
    from .precision_builder import PrecisionBuilder
    _has_precision_builder = True
except ImportError:
    _has_precision_builder = False

# Import new optimization and monitoring modules
try:
    from .optimization_engine import OptimizationEngine
    from .monitoring_agent import MonitoringAgent, AgentManager
    from .benchmark_system import PerformanceBenchmark
    from .optimization_system import ArciTEKOptimizationSystem
    _has_optimization = True
except ImportError:
    _has_optimization = False

__all__ = []

if _has_precision_builder:
    __all__.append('PrecisionBuilder')

if _has_optimization:
    __all__.extend([
        'OptimizationEngine',
        'MonitoringAgent',
        'AgentManager',
        'PerformanceBenchmark',
        'ArciTEKOptimizationSystem'
    ])

