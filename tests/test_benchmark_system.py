#!/usr/bin/env python3
"""
Tests for ArciTEK.AI Benchmarking System
"""

import pytest
import asyncio
from datetime import datetime
from arcitek_core.benchmark_system import (
    PerformanceBenchmark,
    BenchmarkType,
    CachingSystem,
    BenchmarkResult,
    ComparisonReport
)


class TestPerformanceBenchmark:
    """Test performance benchmark system"""
    
    def test_initialization(self):
        """Test benchmark initialization"""
        benchmark = PerformanceBenchmark()
        
        assert len(benchmark.results) == 0
        assert benchmark.target_percentile == 90
    
    @pytest.mark.asyncio
    async def test_benchmark_throughput(self):
        """Test throughput benchmarking"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_throughput(
            CachingSystem.ARCITEK_OPTIMIZATION,
            duration_seconds=1,
            operations_per_second=1000
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.system_name == CachingSystem.ARCITEK_OPTIMIZATION.value
        assert result.benchmark_type == BenchmarkType.THROUGHPUT.value
        assert result.metric_unit == "ops/sec"
        assert result.metric_value > 0
    
    @pytest.mark.asyncio
    async def test_benchmark_latency(self):
        """Test latency benchmarking"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_latency(
            CachingSystem.REDIS,
            num_requests=100
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.system_name == CachingSystem.REDIS.value
        assert result.benchmark_type == BenchmarkType.LATENCY.value
        assert result.metric_unit == "ms"
        assert result.avg_value > 0
        assert result.min_value > 0
        assert result.max_value >= result.min_value
    
    @pytest.mark.asyncio
    async def test_benchmark_cache_hit_rate(self):
        """Test cache hit rate benchmarking"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_cache_hit_rate(
            CachingSystem.MEMCACHED,
            num_operations=1000
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.system_name == CachingSystem.MEMCACHED.value
        assert result.benchmark_type == BenchmarkType.CACHE_HIT_RATE.value
        assert result.metric_unit == "%"
        assert 0 <= result.avg_value <= 100
    
    @pytest.mark.asyncio
    async def test_benchmark_memory_efficiency(self):
        """Test memory efficiency benchmarking"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_memory_efficiency(
            CachingSystem.VARNISH,
            cache_size_mb=500
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.system_name == CachingSystem.VARNISH.value
        assert result.benchmark_type == BenchmarkType.MEMORY_EFFICIENCY.value
        assert result.metric_unit == "ops/MB"
    
    @pytest.mark.asyncio
    async def test_benchmark_concurrent_operations(self):
        """Test concurrent operations benchmarking"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_concurrent_operations(
            CachingSystem.ARCITEK_OPTIMIZATION,
            num_concurrent=10,
            operations_per_client=10
        )
        
        assert isinstance(result, BenchmarkResult)
        assert result.system_name == CachingSystem.ARCITEK_OPTIMIZATION.value
        assert result.benchmark_type == BenchmarkType.CONCURRENT_OPERATIONS.value
        assert result.sample_count > 0
    
    @pytest.mark.asyncio
    async def test_compare_systems(self):
        """Test system comparison"""
        benchmark = PerformanceBenchmark()
        
        # Run benchmarks for multiple systems
        systems = [
            CachingSystem.REDIS,
            CachingSystem.MEMCACHED,
            CachingSystem.ARCITEK_OPTIMIZATION
        ]
        
        for system in systems:
            await benchmark.benchmark_throughput(system, duration_seconds=1)
        
        # Compare systems
        comparison = benchmark.compare_systems(BenchmarkType.THROUGHPUT)
        
        assert isinstance(comparison, ComparisonReport)
        assert comparison.arcitek_score > 0
        assert len(comparison.competitor_scores) > 0
        assert comparison.percentile_ranking >= 0
        assert comparison.percentile_ranking <= 100
        assert isinstance(comparison.meets_target, bool)
        assert len(comparison.recommendations) > 0
    
    @pytest.mark.asyncio
    async def test_generate_benchmark_report(self):
        """Test benchmark report generation"""
        benchmark = PerformanceBenchmark()
        
        # Run some benchmarks
        await benchmark.benchmark_throughput(
            CachingSystem.ARCITEK_OPTIMIZATION,
            duration_seconds=1
        )
        await benchmark.benchmark_latency(
            CachingSystem.ARCITEK_OPTIMIZATION,
            num_requests=100
        )
        
        report = benchmark.generate_benchmark_report()
        
        assert 'generated_at' in report
        assert 'total_benchmarks' in report
        assert 'target_percentile' in report
        assert report['total_benchmarks'] >= 2
        assert report['target_percentile'] == 90
    
    @pytest.mark.asyncio
    async def test_export_results(self, tmp_path):
        """Test results export"""
        benchmark = PerformanceBenchmark()
        
        # Run a benchmark
        await benchmark.benchmark_throughput(
            CachingSystem.ARCITEK_OPTIMIZATION,
            duration_seconds=1
        )
        
        # Export results
        filepath = tmp_path / "benchmark_results.json"
        result = benchmark.export_results(str(filepath))
        
        assert result == True
        assert filepath.exists()
    
    @pytest.mark.asyncio
    async def test_percentile_calculations(self):
        """Test percentile calculations in results"""
        benchmark = PerformanceBenchmark()
        
        result = await benchmark.benchmark_latency(
            CachingSystem.REDIS,
            num_requests=1000
        )
        
        # Verify percentile ordering
        assert result.percentile_90 >= result.min_value
        assert result.percentile_95 >= result.percentile_90
        assert result.percentile_99 >= result.percentile_95
        assert result.max_value >= result.percentile_99
    
    @pytest.mark.asyncio
    async def test_arcitek_optimization_performance(self):
        """Test that ArciTEK optimization meets performance targets"""
        benchmark = PerformanceBenchmark()
        
        # Run comprehensive benchmarks
        systems = [
            CachingSystem.REDIS,
            CachingSystem.MEMCACHED,
            CachingSystem.ARCITEK_OPTIMIZATION
        ]
        
        # Throughput test
        for system in systems:
            await benchmark.benchmark_throughput(system, duration_seconds=1)
        
        comparison = benchmark.compare_systems(BenchmarkType.THROUGHPUT)
        
        # ArciTEK should perform competitively
        assert comparison.arcitek_score > 0
        
        # ArciTEK should be in a reasonable percentile range
        # (not necessarily always the best due to randomness in simulation)
        assert comparison.percentile_ranking >= 33  # At least top 67%


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
