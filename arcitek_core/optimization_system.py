#!/usr/bin/env python3
"""
ArciTEK.AI Optimization & Agent System - Main Integration Module
Integrates optimization engine, monitoring agents, and benchmarking
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from optimization_engine import OptimizationEngine, OptimizationLevel
from monitoring_agent import (
    MonitoringAgent, AgentManager, SecurityLevel
)
from benchmark_system import PerformanceBenchmark, CachingSystem, BenchmarkType
from gcp_deployment import GCPDeployment, GCPConfig, DeploymentEnvironment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ArciTEKOptimizationSystem:
    """Main integration class for ArciTEK.AI optimization and agent system"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config = self._load_config(config_file)
        self.optimization_engine = None
        self.agent_manager = None
        self.benchmark_system = None
        self.running = False
        
    def _load_config(self, config_file: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            'optimization_engine': {
                'optimization_level': 'ml_powered',
                'auto_apply': False,
                'monitoring_interval_seconds': 60,
                'alert_thresholds': {
                    'hit_rate_min': 0.8,
                    'latency_max_ms': 100,
                    'memory_usage_max_mb': 1024
                }
            },
            'monitoring_agents': {
                'engine_endpoint': 'https://optimization-engine.arcitek.ai',
                'security_level': 'sha512',
                'monitoring_interval': 60,
                'shared_secret': 'ArciTEK-Secure-2025'
            },
            'benchmarking': {
                'target_percentile': 90,
                'benchmark_interval_hours': 24,
                'systems_to_compare': ['redis', 'memcached', 'varnish', 'nginx']
            },
            'deployment': {
                'platform': 'gcp',
                'environment': 'production',
                'auto_deploy': False
            }
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    default_config.update(user_config)
                logger.info(f"Configuration loaded from {config_file}")
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}. Using defaults.")
        
        return default_config
    
    async def initialize(self) -> bool:
        """Initialize all components"""
        try:
            logger.info("Initializing ArciTEK.AI Optimization System...")
            
            # Initialize optimization engine
            logger.info("Initializing Optimization Engine...")
            engine_config = self.config['optimization_engine']
            self.optimization_engine = OptimizationEngine(config=engine_config)
            
            # Initialize agent manager
            logger.info("Initializing Agent Manager...")
            agent_config = self.config['monitoring_agents']
            self.agent_manager = AgentManager(
                engine_endpoint=agent_config['engine_endpoint']
            )
            
            # Register default agent for local system
            security_level = SecurityLevel[agent_config['security_level'].upper()]
            agent = self.agent_manager.register_agent(
                agent_id="agent-local-001",
                security_level=security_level,
                monitoring_interval=agent_config['monitoring_interval']
            )
            agent.initialize(shared_secret=agent_config['shared_secret'])
            
            # Initialize benchmark system
            logger.info("Initializing Benchmark System...")
            self.benchmark_system = PerformanceBenchmark()
            
            logger.info("✓ All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            return False
    
    async def start_optimization(self, target_system: str = "production") -> None:
        """Start optimization engine monitoring"""
        if not self.optimization_engine:
            logger.error("Optimization engine not initialized")
            return
        
        logger.info(f"Starting optimization for {target_system}...")
        self.running = True
        
        try:
            await self.optimization_engine.start_monitoring(target_system)
        except Exception as e:
            logger.error(f"Error in optimization: {e}")
            self.running = False
    
    async def start_agents(self) -> None:
        """Start monitoring agents"""
        if not self.agent_manager:
            logger.error("Agent manager not initialized")
            return
        
        logger.info("Starting monitoring agents...")
        
        try:
            shared_secret = self.config['monitoring_agents']['shared_secret']
            await self.agent_manager.start_all_agents(shared_secret)
        except Exception as e:
            logger.error(f"Error starting agents: {e}")
    
    async def run_benchmarks(self, full_suite: bool = False) -> Dict[str, Any]:
        """Run performance benchmarks"""
        if not self.benchmark_system:
            logger.error("Benchmark system not initialized")
            return {}
        
        logger.info("Running performance benchmarks...")
        
        # Systems to benchmark
        systems = [CachingSystem.ARCITEK_OPTIMIZATION]
        systems_config = self.config['benchmarking']['systems_to_compare']
        
        for system_name in systems_config:
            try:
                systems.append(CachingSystem[system_name.upper()])
            except KeyError:
                logger.warning(f"Unknown caching system: {system_name}")
        
        results = {}
        
        try:
            # Run throughput benchmarks
            logger.info("Benchmarking throughput...")
            for system in systems:
                result = await self.benchmark_system.benchmark_throughput(
                    system, duration_seconds=10 if not full_suite else 60
                )
                results[f"{system.value}_throughput"] = result
            
            # Run latency benchmarks
            logger.info("Benchmarking latency...")
            for system in systems:
                result = await self.benchmark_system.benchmark_latency(
                    system, num_requests=1000 if not full_suite else 10000
                )
                results[f"{system.value}_latency"] = result
            
            # Run cache hit rate benchmarks
            logger.info("Benchmarking cache hit rate...")
            for system in systems:
                result = await self.benchmark_system.benchmark_cache_hit_rate(
                    system, num_operations=10000 if not full_suite else 100000
                )
                results[f"{system.value}_hit_rate"] = result
            
            # Generate comparison report
            logger.info("Generating benchmark report...")
            report = self.benchmark_system.generate_benchmark_report()
            
            return report
            
        except Exception as e:
            logger.error(f"Benchmark error: {e}")
            return {}
    
    async def run(self, duration_seconds: Optional[int] = None) -> None:
        """Run the complete system"""
        if not await self.initialize():
            logger.error("Failed to initialize system")
            return
        
        logger.info("=" * 80)
        logger.info("ArciTEK.AI Optimization & Agent System")
        logger.info("=" * 80)
        
        # Start optimization engine
        optimization_task = asyncio.create_task(
            self.start_optimization("production-cache")
        )
        
        # Start monitoring agents
        await self.start_agents()
        
        # Run initial benchmarks
        benchmark_report = await self.run_benchmarks(full_suite=False)
        
        if benchmark_report:
            logger.info("\n" + "=" * 80)
            logger.info("INITIAL BENCHMARK RESULTS")
            logger.info("=" * 80)
            logger.info(json.dumps(benchmark_report, indent=2))
        
        # Run for specified duration or until interrupted
        try:
            if duration_seconds:
                logger.info(f"Running for {duration_seconds} seconds...")
                await asyncio.sleep(duration_seconds)
            else:
                logger.info("Running indefinitely. Press Ctrl+C to stop.")
                while self.running:
                    await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        
        # Stop all components
        await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shutdown all components gracefully"""
        logger.info("Shutting down ArciTEK.AI Optimization System...")
        
        # Stop optimization engine
        if self.optimization_engine:
            self.optimization_engine.stop_monitoring()
            
            # Generate final report
            logger.info("Generating final optimization report...")
            report = self.optimization_engine.generate_report()
            
            # Save report
            report_file = f"/tmp/optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Optimization report saved to {report_file}")
        
        # Stop agents
        if self.agent_manager:
            self.agent_manager.stop_all_agents()
        
        # Export benchmark results
        if self.benchmark_system and self.benchmark_system.results:
            results_file = f"/tmp/benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            self.benchmark_system.export_results(results_file)
            logger.info(f"Benchmark results saved to {results_file}")
        
        self.running = False
        logger.info("✓ Shutdown complete")
    
    def generate_deployment_config(
        self,
        environment: str = "production",
        output_dir: str = "./gcp-deployment"
    ) -> bool:
        """Generate Google Cloud deployment configuration"""
        try:
            logger.info(f"Generating GCP deployment configuration for {environment}...")
            
            # Create GCP configuration
            config = GCPConfig(
                project_id="arcitek-ai-production",
                region="us-central1",
                zone="us-central1-a",
                cluster_name=f"arcitek-gke-{environment}",
                node_count=3,
                machine_type="n1-standard-4",
                disk_size_gb=100,
                auto_scaling=True,
                min_nodes=3,
                max_nodes=10
            )
            
            # Create deployment manager
            env = DeploymentEnvironment[environment.upper()]
            deployment = GCPDeployment(config, env)
            
            # Save all manifests
            success = deployment.save_manifests(output_dir)
            
            if success:
                logger.info(f"✓ Deployment configuration saved to {output_dir}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to generate deployment config: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='ArciTEK.AI Optimization & Agent System'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        help='Path to configuration file (JSON)'
    )
    
    parser.add_argument(
        '--duration',
        type=int,
        help='Run duration in seconds (default: run indefinitely)'
    )
    
    parser.add_argument(
        '--benchmark-only',
        action='store_true',
        help='Run benchmarks only and exit'
    )
    
    parser.add_argument(
        '--generate-deployment',
        type=str,
        choices=['development', 'staging', 'production'],
        help='Generate GCP deployment configuration'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='./gcp-deployment',
        help='Output directory for deployment files'
    )
    
    args = parser.parse_args()
    
    # Create system instance
    system = ArciTEKOptimizationSystem(config_file=args.config)
    
    # Handle deployment generation
    if args.generate_deployment:
        success = system.generate_deployment_config(
            environment=args.generate_deployment,
            output_dir=args.output_dir
        )
        sys.exit(0 if success else 1)
    
    # Handle benchmark-only mode
    if args.benchmark_only:
        async def run_benchmarks():
            await system.initialize()
            report = await system.run_benchmarks(full_suite=True)
            print("\n" + "=" * 80)
            print("BENCHMARK REPORT")
            print("=" * 80)
            print(json.dumps(report, indent=2))
        
        asyncio.run(run_benchmarks())
        sys.exit(0)
    
    # Run the complete system
    try:
        asyncio.run(system.run(duration_seconds=args.duration))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
