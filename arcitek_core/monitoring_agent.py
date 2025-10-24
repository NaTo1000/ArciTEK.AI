#!/usr/bin/env python3
"""
ArciTEK.AI Monitoring Agent System
Lightweight agents for customer systems monitoring with secure communication
"""

import os
import json
import asyncio
import hashlib
import hmac
import time
import socket
import psutil
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import threading
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    REPORTING = "reporting"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class SecurityLevel(Enum):
    BASIC = "basic"
    SHA512 = "sha512"
    RSA_2048 = "rsa_2048"
    RSA_4096 = "rsa_4096"


@dataclass
class SystemMetrics:
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_available_gb: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int
    timestamp: datetime


@dataclass
class CacheStatus:
    cache_name: str
    size_mb: float
    hit_rate: float
    miss_rate: float
    entries_count: int
    avg_access_time_ms: float
    timestamp: datetime


@dataclass
class AgentReport:
    agent_id: str
    hostname: str
    status: str
    system_metrics: SystemMetrics
    cache_statuses: List[CacheStatus]
    uptime_seconds: float
    report_timestamp: datetime
    signature: Optional[str] = None


class SecureAuthenticator:
    """Handles secure authentication using SHA512 and RSA"""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.SHA512):
        self.security_level = security_level
        self.private_key = None
        self.public_key = None
        self.shared_secret = None
        
        if security_level in [SecurityLevel.RSA_2048, SecurityLevel.RSA_4096]:
            self._generate_rsa_keys()
    
    def _generate_rsa_keys(self) -> None:
        """Generate RSA key pair"""
        key_size = 2048 if self.security_level == SecurityLevel.RSA_2048 else 4096
        
        logger.info(f"Generating RSA-{key_size} key pair...")
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        logger.info("RSA key pair generated successfully")
    
    def set_shared_secret(self, secret: str) -> None:
        """Set shared secret for SHA512 authentication"""
        self.shared_secret = secret.encode('utf-8')
    
    def sign_message(self, message: str) -> str:
        """Sign message with SHA512 or RSA"""
        if self.security_level == SecurityLevel.SHA512:
            return self._sign_sha512(message)
        elif self.security_level in [SecurityLevel.RSA_2048, SecurityLevel.RSA_4096]:
            return self._sign_rsa(message)
        else:
            return hashlib.md5(message.encode()).hexdigest()
    
    def _sign_sha512(self, message: str) -> str:
        """Sign message with SHA512 HMAC"""
        if not self.shared_secret:
            raise ValueError("Shared secret not set for SHA512 authentication")
        
        signature = hmac.new(
            self.shared_secret,
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature
    
    def _sign_rsa(self, message: str) -> str:
        """Sign message with RSA"""
        if not self.private_key:
            raise ValueError("RSA private key not available")
        
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        return signature.hex()
    
    def verify_signature(self, message: str, signature: str) -> bool:
        """Verify message signature"""
        try:
            if self.security_level == SecurityLevel.SHA512:
                expected_sig = self._sign_sha512(message)
                return hmac.compare_digest(expected_sig, signature)
            elif self.security_level in [SecurityLevel.RSA_2048, SecurityLevel.RSA_4096]:
                self.public_key.verify(
                    bytes.fromhex(signature),
                    message.encode('utf-8'),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                return True
            else:
                return True
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def export_public_key(self) -> Optional[str]:
        """Export public key for RSA"""
        if not self.public_key:
            return None
        
        pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return pem.decode('utf-8')


class MonitoringAgent:
    """Lightweight monitoring agent for customer systems"""
    
    def __init__(
        self,
        agent_id: str,
        engine_endpoint: str,
        security_level: SecurityLevel = SecurityLevel.SHA512,
        monitoring_interval: int = 60
    ):
        self.agent_id = agent_id
        self.engine_endpoint = engine_endpoint
        self.monitoring_interval = monitoring_interval
        self.status = AgentStatus.IDLE
        self.authenticator = SecureAuthenticator(security_level)
        self.start_time = time.time()
        self.monitoring_active = False
        self._lock = threading.Lock()
        self.last_report = None
        
        # Network statistics baseline
        self._net_io_baseline = psutil.net_io_counters()
    
    def initialize(self, shared_secret: Optional[str] = None) -> bool:
        """Initialize agent with authentication"""
        try:
            if shared_secret:
                self.authenticator.set_shared_secret(shared_secret)
            
            logger.info(f"Agent {self.agent_id} initialized successfully")
            logger.info(f"Security level: {self.authenticator.security_level.value}")
            
            # Export public key if using RSA
            public_key = self.authenticator.export_public_key()
            if public_key:
                logger.info("RSA public key generated")
            
            return True
            
        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            return False
    
    async def start_monitoring(self) -> None:
        """Start asynchronous monitoring"""
        self.monitoring_active = True
        self.status = AgentStatus.MONITORING
        logger.info(f"Agent {self.agent_id} started monitoring")
        
        while self.monitoring_active:
            try:
                # Collect metrics
                metrics = await self._collect_system_metrics()
                cache_statuses = await self._collect_cache_statuses()
                
                # Create report
                report = self._create_report(metrics, cache_statuses)
                
                # Send report to engine
                await self._send_report(report)
                
                # Update last report
                with self._lock:
                    self.last_report = report
                
                # Wait for next interval
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                self.status = AgentStatus.ERROR
                await asyncio.sleep(10)
    
    def stop_monitoring(self) -> None:
        """Stop monitoring"""
        self.monitoring_active = False
        self.status = AgentStatus.DISCONNECTED
        logger.info(f"Agent {self.agent_id} stopped monitoring")
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system performance metrics"""
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used_mb = memory.used / (1024 * 1024)
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        disk_usage_percent = disk.percent
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_available_gb = disk.free / (1024 * 1024 * 1024)
        
        # Network I/O
        net_io = psutil.net_io_counters()
        network_sent_mb = (net_io.bytes_sent - self._net_io_baseline.bytes_sent) / (1024 * 1024)
        network_recv_mb = (net_io.bytes_recv - self._net_io_baseline.bytes_recv) / (1024 * 1024)
        
        # Active connections
        active_connections = len(psutil.net_connections())
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_used_mb,
            memory_available_mb=memory_available_mb,
            disk_usage_percent=disk_usage_percent,
            disk_used_gb=disk_used_gb,
            disk_available_gb=disk_available_gb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            active_connections=active_connections,
            timestamp=datetime.now()
        )
    
    async def _collect_cache_statuses(self) -> List[CacheStatus]:
        """Collect cache status information"""
        # Simulate cache status collection
        # In production, this would query Redis, Memcached, etc.
        
        import random
        
        caches = []
        for cache_name in ["redis-cache", "memcached-cache", "app-cache"]:
            caches.append(CacheStatus(
                cache_name=cache_name,
                size_mb=random.uniform(50, 500),
                hit_rate=random.uniform(0.7, 0.95),
                miss_rate=random.uniform(0.05, 0.3),
                entries_count=random.randint(1000, 100000),
                avg_access_time_ms=random.uniform(1, 50),
                timestamp=datetime.now()
            ))
        
        return caches
    
    def _create_report(
        self,
        metrics: SystemMetrics,
        cache_statuses: List[CacheStatus]
    ) -> AgentReport:
        """Create monitoring report"""
        uptime = time.time() - self.start_time
        
        report = AgentReport(
            agent_id=self.agent_id,
            hostname=socket.gethostname(),
            status=self.status.value,
            system_metrics=metrics,
            cache_statuses=cache_statuses,
            uptime_seconds=uptime,
            report_timestamp=datetime.now()
        )
        
        # Sign report
        report_json = self._report_to_json(report)
        signature = self.authenticator.sign_message(report_json)
        report.signature = signature
        
        return report
    
    def _report_to_json(self, report: AgentReport) -> str:
        """Convert report to JSON (excluding signature)"""
        data = {
            'agent_id': report.agent_id,
            'hostname': report.hostname,
            'status': report.status,
            'system_metrics': asdict(report.system_metrics),
            'cache_statuses': [asdict(cs) for cs in report.cache_statuses],
            'uptime_seconds': report.uptime_seconds,
            'report_timestamp': report.report_timestamp.isoformat()
        }
        
        # Convert datetime objects to ISO format
        data['system_metrics']['timestamp'] = data['system_metrics']['timestamp'].isoformat()
        for cs in data['cache_statuses']:
            cs['timestamp'] = cs['timestamp'].isoformat()
        
        return json.dumps(data, sort_keys=True)
    
    async def _send_report(self, report: AgentReport) -> bool:
        """Send report to optimization engine"""
        try:
            self.status = AgentStatus.REPORTING
            
            report_data = {
                'report': self._report_to_json(report),
                'signature': report.signature,
                'security_level': self.authenticator.security_level.value
            }
            
            # Simulate sending to engine
            # In production, use HTTP/HTTPS, gRPC, or message queue
            logger.info(f"Sending report from agent {self.agent_id}")
            logger.debug(f"Report size: {len(json.dumps(report_data))} bytes")
            
            await asyncio.sleep(0.1)  # Simulate network delay
            
            self.status = AgentStatus.MONITORING
            return True
            
        except Exception as e:
            logger.error(f"Failed to send report: {e}")
            self.status = AgentStatus.ERROR
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        with self._lock:
            status = {
                'agent_id': self.agent_id,
                'hostname': socket.gethostname(),
                'status': self.status.value,
                'uptime_seconds': time.time() - self.start_time,
                'monitoring_active': self.monitoring_active,
                'security_level': self.authenticator.security_level.value,
                'last_report_time': self.last_report.report_timestamp.isoformat() if self.last_report else None
            }
        
        return status
    
    def health_check(self) -> Dict[str, Any]:
        """Perform agent health check"""
        try:
            # Check system resources
            cpu = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            health = {
                'healthy': True,
                'agent_id': self.agent_id,
                'status': self.status.value,
                'cpu_usage': cpu,
                'memory_usage': memory.percent,
                'monitoring_active': self.monitoring_active,
                'timestamp': datetime.now().isoformat()
            }
            
            # Check if agent is healthy
            if cpu > 90 or memory.percent > 90:
                health['healthy'] = False
                health['issues'] = []
                
                if cpu > 90:
                    health['issues'].append('High CPU usage')
                if memory.percent > 90:
                    health['issues'].append('High memory usage')
            
            return health
            
        except Exception as e:
            return {
                'healthy': False,
                'agent_id': self.agent_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


class AgentManager:
    """Manages multiple monitoring agents"""
    
    def __init__(self, engine_endpoint: str):
        self.engine_endpoint = engine_endpoint
        self.agents: Dict[str, MonitoringAgent] = {}
        self._lock = threading.Lock()
    
    def register_agent(
        self,
        agent_id: str,
        security_level: SecurityLevel = SecurityLevel.SHA512,
        monitoring_interval: int = 60
    ) -> MonitoringAgent:
        """Register new monitoring agent"""
        with self._lock:
            if agent_id in self.agents:
                logger.warning(f"Agent {agent_id} already registered")
                return self.agents[agent_id]
            
            agent = MonitoringAgent(
                agent_id=agent_id,
                engine_endpoint=self.engine_endpoint,
                security_level=security_level,
                monitoring_interval=monitoring_interval
            )
            
            self.agents[agent_id] = agent
            logger.info(f"Agent {agent_id} registered successfully")
            
            return agent
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister monitoring agent"""
        with self._lock:
            if agent_id not in self.agents:
                logger.warning(f"Agent {agent_id} not found")
                return False
            
            agent = self.agents[agent_id]
            agent.stop_monitoring()
            del self.agents[agent_id]
            
            logger.info(f"Agent {agent_id} unregistered")
            return True
    
    async def start_all_agents(self, shared_secret: str) -> None:
        """Start all registered agents"""
        tasks = []
        
        with self._lock:
            for agent_id, agent in self.agents.items():
                agent.initialize(shared_secret)
                task = asyncio.create_task(agent.start_monitoring())
                tasks.append(task)
        
        logger.info(f"Started {len(tasks)} monitoring agents")
    
    def stop_all_agents(self) -> None:
        """Stop all agents"""
        with self._lock:
            for agent in self.agents.values():
                agent.stop_monitoring()
        
        logger.info("All agents stopped")
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents"""
        with self._lock:
            statuses = {
                agent_id: agent.get_status()
                for agent_id, agent in self.agents.items()
            }
        
        return statuses
    
    def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Health check all agents"""
        with self._lock:
            health_checks = {
                agent_id: agent.health_check()
                for agent_id, agent in self.agents.items()
            }
        
        return health_checks


# Example usage
async def main():
    """Example usage of monitoring agent system"""
    
    # Create agent manager
    manager = AgentManager(engine_endpoint="https://optimization-engine.arcitek.ai")
    
    # Register agents
    agent1 = manager.register_agent(
        "agent-prod-001",
        security_level=SecurityLevel.SHA512,
        monitoring_interval=30
    )
    
    agent2 = manager.register_agent(
        "agent-prod-002",
        security_level=SecurityLevel.RSA_2048,
        monitoring_interval=30
    )
    
    # Start all agents
    await manager.start_all_agents(shared_secret="ArciTEK-Secure-2025")
    
    # Run for 5 minutes
    await asyncio.sleep(300)
    
    # Get statuses
    statuses = manager.get_all_statuses()
    print("Agent Statuses:")
    print(json.dumps(statuses, indent=2))
    
    # Health check
    health = manager.health_check_all()
    print("\nAgent Health:")
    print(json.dumps(health, indent=2))
    
    # Stop all agents
    manager.stop_all_agents()


if __name__ == "__main__":
    asyncio.run(main())
