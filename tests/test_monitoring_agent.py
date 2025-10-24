#!/usr/bin/env python3
"""
Tests for ArciTEK.AI Monitoring Agent System
"""

import pytest
import asyncio
import json
from datetime import datetime
from arcitek_core.monitoring_agent import (
    MonitoringAgent,
    AgentManager,
    SecureAuthenticator,
    AgentStatus,
    SecurityLevel,
    SystemMetrics,
    CacheStatus,
    AgentReport
)


class TestSecureAuthenticator:
    """Test secure authentication"""
    
    def test_initialization_sha512(self):
        """Test SHA512 authenticator initialization"""
        auth = SecureAuthenticator(SecurityLevel.SHA512)
        assert auth.security_level == SecurityLevel.SHA512
        assert auth.shared_secret is None
    
    def test_initialization_rsa(self):
        """Test RSA authenticator initialization"""
        auth = SecureAuthenticator(SecurityLevel.RSA_2048)
        assert auth.security_level == SecurityLevel.RSA_2048
        assert auth.private_key is not None
        assert auth.public_key is not None
    
    def test_set_shared_secret(self):
        """Test setting shared secret"""
        auth = SecureAuthenticator(SecurityLevel.SHA512)
        auth.set_shared_secret("test-secret-123")
        assert auth.shared_secret is not None
    
    def test_sign_message_sha512(self):
        """Test message signing with SHA512"""
        auth = SecureAuthenticator(SecurityLevel.SHA512)
        auth.set_shared_secret("test-secret-123")
        
        message = "test message"
        signature = auth.sign_message(message)
        
        assert signature is not None
        assert len(signature) > 0
    
    def test_sign_message_rsa(self):
        """Test message signing with RSA"""
        auth = SecureAuthenticator(SecurityLevel.RSA_2048)
        
        message = "test message"
        signature = auth.sign_message(message)
        
        assert signature is not None
        assert len(signature) > 0
    
    def test_verify_signature_sha512(self):
        """Test signature verification with SHA512"""
        auth = SecureAuthenticator(SecurityLevel.SHA512)
        auth.set_shared_secret("test-secret-123")
        
        message = "test message"
        signature = auth.sign_message(message)
        
        # Verify correct signature
        assert auth.verify_signature(message, signature) == True
        
        # Verify incorrect signature
        assert auth.verify_signature(message, "invalid-signature") == False
    
    def test_verify_signature_rsa(self):
        """Test signature verification with RSA"""
        auth = SecureAuthenticator(SecurityLevel.RSA_2048)
        
        message = "test message"
        signature = auth.sign_message(message)
        
        # Verify correct signature
        assert auth.verify_signature(message, signature) == True
    
    def test_export_public_key(self):
        """Test public key export"""
        auth = SecureAuthenticator(SecurityLevel.RSA_2048)
        
        public_key_pem = auth.export_public_key()
        
        assert public_key_pem is not None
        assert "BEGIN PUBLIC KEY" in public_key_pem
        assert "END PUBLIC KEY" in public_key_pem


class TestMonitoringAgent:
    """Test monitoring agent"""
    
    def test_initialization(self):
        """Test agent initialization"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com",
            security_level=SecurityLevel.SHA512,
            monitoring_interval=30
        )
        
        assert agent.agent_id == "test-agent-001"
        assert agent.engine_endpoint == "https://test.example.com"
        assert agent.monitoring_interval == 30
        assert agent.status == AgentStatus.IDLE
    
    def test_initialize_with_secret(self):
        """Test agent initialization with shared secret"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        
        result = agent.initialize(shared_secret="test-secret-123")
        
        assert result == True
        assert agent.authenticator.shared_secret is not None
    
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self):
        """Test system metrics collection"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        
        metrics = await agent._collect_system_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent >= 0
        assert metrics.memory_percent >= 0
        assert metrics.memory_used_mb >= 0
        assert metrics.memory_available_mb >= 0
        assert metrics.disk_usage_percent >= 0
    
    @pytest.mark.asyncio
    async def test_collect_cache_statuses(self):
        """Test cache status collection"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        
        statuses = await agent._collect_cache_statuses()
        
        assert isinstance(statuses, list)
        assert len(statuses) > 0
        assert all(isinstance(s, CacheStatus) for s in statuses)
    
    @pytest.mark.asyncio
    async def test_create_report(self):
        """Test report creation"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        agent.initialize(shared_secret="test-secret")
        
        metrics = await agent._collect_system_metrics()
        cache_statuses = await agent._collect_cache_statuses()
        
        report = agent._create_report(metrics, cache_statuses)
        
        assert isinstance(report, AgentReport)
        assert report.agent_id == "test-agent-001"
        assert report.signature is not None
    
    def test_get_status(self):
        """Test agent status retrieval"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        
        status = agent.get_status()
        
        assert 'agent_id' in status
        assert 'hostname' in status
        assert 'status' in status
        assert 'uptime_seconds' in status
    
    def test_health_check(self):
        """Test agent health check"""
        agent = MonitoringAgent(
            agent_id="test-agent-001",
            engine_endpoint="https://test.example.com"
        )
        
        health = agent.health_check()
        
        assert 'healthy' in health
        assert 'agent_id' in health
        assert 'status' in health
        assert 'timestamp' in health


class TestAgentManager:
    """Test agent manager"""
    
    def test_initialization(self):
        """Test manager initialization"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        assert manager.engine_endpoint == "https://test.example.com"
        assert len(manager.agents) == 0
    
    def test_register_agent(self):
        """Test agent registration"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        agent = manager.register_agent(
            agent_id="test-agent-001",
            security_level=SecurityLevel.SHA512,
            monitoring_interval=60
        )
        
        assert agent is not None
        assert agent.agent_id == "test-agent-001"
        assert "test-agent-001" in manager.agents
    
    def test_register_duplicate_agent(self):
        """Test registering duplicate agent"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        agent1 = manager.register_agent("test-agent-001")
        agent2 = manager.register_agent("test-agent-001")
        
        assert agent1 == agent2
        assert len(manager.agents) == 1
    
    def test_unregister_agent(self):
        """Test agent unregistration"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        manager.register_agent("test-agent-001")
        assert len(manager.agents) == 1
        
        result = manager.unregister_agent("test-agent-001")
        
        assert result == True
        assert len(manager.agents) == 0
    
    def test_unregister_nonexistent_agent(self):
        """Test unregistering nonexistent agent"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        result = manager.unregister_agent("nonexistent-agent")
        
        assert result == False
    
    def test_get_all_statuses(self):
        """Test getting all agent statuses"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        manager.register_agent("test-agent-001")
        manager.register_agent("test-agent-002")
        
        statuses = manager.get_all_statuses()
        
        assert len(statuses) == 2
        assert "test-agent-001" in statuses
        assert "test-agent-002" in statuses
    
    def test_health_check_all(self):
        """Test health check for all agents"""
        manager = AgentManager(engine_endpoint="https://test.example.com")
        
        manager.register_agent("test-agent-001")
        manager.register_agent("test-agent-002")
        
        health_checks = manager.health_check_all()
        
        assert len(health_checks) == 2
        assert "test-agent-001" in health_checks
        assert "test-agent-002" in health_checks
        assert all('healthy' in h for h in health_checks.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
