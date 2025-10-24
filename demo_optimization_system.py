#!/usr/bin/env python3
"""
ArciTEK.AI Optimization & Agent System - Quick Demo
Demonstrates the optimization engine, monitoring agents, and benchmarking
"""

import asyncio
import json
import logging
from datetime import datetime

from arcitek_core.optimization_engine import OptimizationEngine
from arcitek_core.monitoring_agent import AgentManager, SecurityLevel
from arcitek_core.benchmark_system import PerformanceBenchmark, CachingSystem, BenchmarkType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_optimization_engine():
    """Demonstrate optimization engine capabilities"""
    print("\n" + "="*80)
    print("OPTIMIZATION ENGINE DEMO")
    print("="*80)
    
    # Create engine
    engine = OptimizationEngine()
    
    # Start monitoring (run for 30 seconds)
    monitoring_task = asyncio.create_task(
        engine.start_monitoring("demo-cache-system")
    )
    
    logger.info("Monitoring started. Collecting metrics for 30 seconds...")
    await asyncio.sleep(30)
    
    # Stop monitoring
    engine.stop_monitoring()
    await monitoring_task
    
    # Generate report
    report = engine.generate_report()
    
    print("\n" + "-"*80)
    print("OPTIMIZATION REPORT")
    print("-"*80)
    print(json.dumps(report, indent=2))
    
    # Export metrics
    metrics_file = f"/tmp/demo_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    engine.export_metrics(metrics_file)
    logger.info(f"Metrics exported to {metrics_file}")
    
    return engine


async def demo_monitoring_agents():
    """Demonstrate monitoring agent system"""
    print("\n" + "="*80)
    print("MONITORING AGENT DEMO")
    print("="*80)
    
    # Create agent manager
    manager = AgentManager(engine_endpoint="http://localhost:8080")
    
    # Register multiple agents
    agent1 = manager.register_agent(
        "demo-agent-001",
        security_level=SecurityLevel.SHA512,
        monitoring_interval=10
    )
    
    agent2 = manager.register_agent(
        "demo-agent-002",
        security_level=SecurityLevel.RSA_2048,
        monitoring_interval=10
    )
    
    # Initialize agents
    agent1.initialize(shared_secret="demo-secret-123")
    agent2.initialize(shared_secret="demo-secret-123")
    
    # Get statuses
    statuses = manager.get_all_statuses()
    
    print("\n" + "-"*80)
    print("AGENT STATUSES")
    print("-"*80)
    print(json.dumps(statuses, indent=2))
    
    # Health check
    health = manager.health_check_all()
    
    print("\n" + "-"*80)
    print("AGENT HEALTH CHECKS")
    print("-"*80)
    print(json.dumps(health, indent=2))
    
    return manager


async def demo_benchmarking():
    """Demonstrate benchmarking system"""
    print("\n" + "="*80)
    print("BENCHMARKING DEMO")
    print("="*80)
    
    benchmark = PerformanceBenchmark()
    
    # Systems to benchmark
    systems = [
        CachingSystem.REDIS,
        CachingSystem.MEMCACHED,
        CachingSystem.ARCITEK_OPTIMIZATION
    ]
    
    logger.info("Running throughput benchmarks...")
    for system in systems:
        await benchmark.benchmark_throughput(system, duration_seconds=5)
    
    logger.info("Running latency benchmarks...")
    for system in systems:
        await benchmark.benchmark_latency(system, num_requests=500)
    
    logger.info("Running cache hit rate benchmarks...")
    for system in systems:
        await benchmark.benchmark_cache_hit_rate(system, num_operations=5000)
    
    # Generate report
    report = benchmark.generate_benchmark_report()
    
    print("\n" + "-"*80)
    print("BENCHMARK REPORT")
    print("-"*80)
    print(json.dumps(report, indent=2))
    
    # Export results
    results_file = f"/tmp/demo_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    benchmark.export_results(results_file)
    logger.info(f"Benchmark results exported to {results_file}")
    
    # Show comparison for throughput
    try:
        comparison = benchmark.compare_systems(BenchmarkType.THROUGHPUT)
        
        print("\n" + "-"*80)
        print("THROUGHPUT COMPARISON")
        print("-"*80)
        print(f"ArciTEK Score: {comparison.arcitek_score:.2f}")
        print(f"Percentile Ranking: {comparison.percentile_ranking}%")
        print(f"Meets 90th Percentile Target: {comparison.meets_target}")
        print("\nPerformance Advantage:")
        for system, advantage in comparison.performance_advantage.items():
            print(f"  {system}: {advantage:+.2f}%")
        print("\nRecommendations:")
        for rec in comparison.recommendations:
            print(f"  • {rec}")
    except ValueError as e:
        logger.warning(f"Could not generate comparison: {e}")
    
    return benchmark


async def main():
    """Run complete demo"""
    print("\n" + "="*80)
    print("ArciTEK.AI OPTIMIZATION & AGENT SYSTEM - QUICK DEMO")
    print("="*80)
    print("\nThis demo showcases:")
    print("1. Optimization Engine - ML-powered cache optimization")
    print("2. Monitoring Agents - Secure system monitoring")
    print("3. Benchmarking System - Performance comparison")
    print("\n" + "="*80)
    
    try:
        # Run demos
        engine = await demo_optimization_engine()
        manager = await demo_monitoring_agents()
        benchmark = await demo_benchmarking()
        
        # Summary
        print("\n" + "="*80)
        print("DEMO SUMMARY")
        print("="*80)
        
        print("\n✓ Optimization Engine:")
        print(f"  - Metrics collected: {len(engine.metrics_history)}")
        print(f"  - Bottlenecks detected: {len(engine.bottlenecks)}")
        print(f"  - Recommendations generated: {len(engine.recommendations)}")
        
        print("\n✓ Monitoring Agents:")
        print(f"  - Agents registered: {len(manager.agents)}")
        print(f"  - All agents healthy: {all(h['healthy'] for h in manager.health_check_all().values())}")
        
        print("\n✓ Benchmarking:")
        print(f"  - Benchmarks completed: {len(benchmark.results)}")
        if benchmark.results:
            report = benchmark.generate_benchmark_report()
            if 'overall_performance' in report:
                print(f"  - Average percentile: {report['overall_performance']['average_percentile']:.1f}%")
                print(f"  - Meets target overall: {report['overall_performance']['meets_target_overall']}")
        
        print("\n" + "="*80)
        print("DEMO COMPLETED SUCCESSFULLY!")
        print("="*80)
        
        print("\nNext steps:")
        print("  1. Review exported metrics and benchmark results in /tmp/")
        print("  2. Generate GCP deployment: python arcitek_core/optimization_system.py --generate-deployment production")
        print("  3. Read documentation: docs/OPTIMIZATION_SYSTEM.md")
        print("\n")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
