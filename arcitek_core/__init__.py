"""
ArciTEK.AI Core Module
The Ultimate Quantum-Enhanced Precision Build System

This module contains the core functionality for ArciTEK.AI including:
- Quantum-enhanced AI orchestration
- Precision build system
- NayDoeV1 learning integration
- Multi-platform compatibility
- Quantum mesh builder with multi-agent coordination (NaTo1000/Multi-Agent#12)
- Nvidia GPU / CUDA / TensorRT / RTX graphics engine
"""

__version__ = "7.1.0"
__author__ = "NaTo1000"
__description__ = "ArciTEK.AI - The Ultimate Quantum-Enhanced Precision Build System"

from .quantum_orchestrator import QuantumOrchestrator
from .ai_model_manager import AIModelManager
from .precision_builder import PrecisionBuilder
from .naydoev1_interface import NayDoeV1Interface
from .quantum_mesh_builder import (
    QuantumMeshBuilder,
    QuantumMeshNode,
    MeshTopology,
    NodeRole,
    EntanglementProtocol,
    DistributedQuantumTask,
    MeshHealthReport,
    MultiAgentCoordinationPlan,
)
from .nvidia_graphics_engine import (
    NvidiaGraphicsEngine,
    GpuDevice,
    NvidiaArchitecture,
    CudaComputeCapability,
    RenderBackend,
    DLSSMode,
    TensorRTPrecision,
    TensorRTEngine,
    RayTracingPipeline,
    DLSSConfig,
    NvidiaGraphicsReport,
)

__all__ = [
    # Original exports
    'QuantumOrchestrator',
    'AIModelManager',
    'PrecisionBuilder',
    'NayDoeV1Interface',
    # Quantum mesh builder
    'QuantumMeshBuilder',
    'QuantumMeshNode',
    'MeshTopology',
    'NodeRole',
    'EntanglementProtocol',
    'DistributedQuantumTask',
    'MeshHealthReport',
    'MultiAgentCoordinationPlan',
    # Nvidia graphics engine
    'NvidiaGraphicsEngine',
    'GpuDevice',
    'NvidiaArchitecture',
    'CudaComputeCapability',
    'RenderBackend',
    'DLSSMode',
    'TensorRTPrecision',
    'TensorRTEngine',
    'RayTracingPipeline',
    'DLSSConfig',
    'NvidiaGraphicsReport',
]

