"""Robotics engineering-plan MVP: domain, orchestration, formats, rules.

Stdlib-only, dependency-free package implementing:

* ``repository`` -- thread-safe SQLite project/revision store with
  immutable revisions, rollback-as-new-revision, and human approval gating.
* ``knowledge`` -- append-only temporal knowledge, provenance, tags,
  citations, relationships, and bounded context retrieval.
* ``orchestrator`` -- dependency-aware, parallel expert-task orchestrator
  that only produces structured plan data (no code execution, no external
  AI calls).
* ``formats`` -- neutral engineering exchange format registry/adapters
  (STEP, STL, DXF, URDF, Gerber, IPC-2581, netlist) limited to metadata
  validation and safe import/export manifests.
* ``rules`` -- rule-based flaw detection for clearances/collisions, wiring
  connectivity/electrical limits, and hydraulic pressure/flow constraints.
* ``simulation`` -- adapter interfaces for FreeCAD, KiCad and ROS 2/Gazebo
  limited to capability manifests and deterministic dry runs.

This is an MVP: automated findings are heuristic, bounded-confidence, and
never claim complete or certified accuracy. Any release/final state
requires an explicit human approval action.
"""

from . import formats, intent, knowledge, orchestrator, repository, rules, simulation
from .intent import IntentAlignmentEngine
from .knowledge import KnowledgeRepository
from .repository import ProjectRepository
from .orchestrator import ExpertPlanOrchestrator

__all__ = [
    "formats",
    "intent",
    "knowledge",
    "orchestrator",
    "repository",
    "rules",
    "simulation",
    "ProjectRepository",
    "KnowledgeRepository",
    "ExpertPlanOrchestrator",
    "IntentAlignmentEngine",
]
