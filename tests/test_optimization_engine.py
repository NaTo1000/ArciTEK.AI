#!/usr/bin/env python3
"""
Tests for ArciTEK.AI Optimization Engine
"""

import pytest
import asyncio
import json
from datetime import datetime
from arcitek_core.optimization_engine import (
    OptimizationEngine,
    MLCachePredictor,
    CacheMetrics,
    OptimizationRecommendation,
    PerformanceBottleneck,
    OptimizationLevel
)


class TestMLCachePredictor:
    """Test ML cache predictor"""
    
    def test_initialization(self):
        """Test predictor initialization"""
        predictor = MLCachePredictor()
        assert predictor.model_trained == False
        assert len(predictor.training_data) == 0
    
    def test_training(self):
        """Test model training"""
        predictor = MLCachePredictor()
        
        # Create sample metrics
        metrics = [
            CacheMetrics(
                hit_rate=0.8 + i * 0.01,
                miss_rate=0.2 - i * 0.01,
                avg_latency_ms=50.0 + i,
                memory_usage_mb=500.0 + i * 10,
                throughput_qps=1000.0 + i * 100,
                eviction_rate=0.1,
                timestamp=datetime.now()
            )
            for i in range(15)
        ]
        
        result = predictor.train(metrics)
        assert result == True
        assert predictor.model_trained == True
        assert len(predictor.training_data) == 15
    
    def test_insufficient_training_data(self):
        """Test training with insufficient data"""
        predictor = MLCachePredictor()
        
        # Only 5 samples (need at least 10)
        metrics = [
            CacheMetrics(
                hit_rate=0.8,
                miss_rate=0.2,
                avg_latency_ms=50.0,
                memory_usage_mb=500.0,
                throughput_qps=1000.0,
                eviction_rate=0.1,
                timestamp=datetime.now()
            )
            for _ in range(5)
        ]
        
        result = predictor.train(metrics)
        assert result == False
        assert predictor.model_trained == False
    
    def test_predict_optimal_size(self):
        """Test optimal cache size prediction"""
        predictor = MLCachePredictor()
        
        current_metrics = CacheMetrics(
            hit_rate=0.75,
            miss_rate=0.25,
            avg_latency_ms=80.0,
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.15,
            timestamp=datetime.now()
        )
        
        size = predictor.predict_optimal_size(current_metrics)
        assert size > 0
        assert isinstance(size, int)
    
    def test_predict_optimal_ttl(self):
        """Test optimal TTL prediction"""
        predictor = MLCachePredictor()
        
        current_metrics = CacheMetrics(
            hit_rate=0.85,
            miss_rate=0.15,
            avg_latency_ms=50.0,
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.05,
            timestamp=datetime.now()
        )
        
        ttl = predictor.predict_optimal_ttl(current_metrics)
        assert ttl > 0
        assert isinstance(ttl, int)


class TestOptimizationEngine:
    """Test optimization engine"""
    
    def test_initialization(self):
        """Test engine initialization"""
        engine = OptimizationEngine()
        assert engine.config is not None
        assert engine.ml_predictor is not None
        assert len(engine.metrics_history) == 0
        assert engine.monitoring_active == False
    
    def test_custom_config(self):
        """Test engine with custom configuration"""
        config = {
            'optimization_level': 'advanced',
            'auto_apply': True,
            'monitoring_interval_seconds': 30
        }
        
        engine = OptimizationEngine(config=config)
        assert engine.config['optimization_level'] == 'advanced'
        assert engine.config['auto_apply'] == True
        assert engine.config['monitoring_interval_seconds'] == 30
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self):
        """Test metrics collection"""
        engine = OptimizationEngine()
        
        metrics = await engine._collect_metrics("test-system")
        
        assert isinstance(metrics, CacheMetrics)
        assert 0 <= metrics.hit_rate <= 1
        assert 0 <= metrics.miss_rate <= 1
        assert metrics.avg_latency_ms > 0
        assert metrics.memory_usage_mb > 0
        assert metrics.throughput_qps > 0
    
    def test_store_metrics(self):
        """Test metrics storage"""
        engine = OptimizationEngine()
        
        metrics = CacheMetrics(
            hit_rate=0.85,
            miss_rate=0.15,
            avg_latency_ms=50.0,
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.05,
            timestamp=datetime.now()
        )
        
        engine._store_metrics(metrics)
        
        assert len(engine.metrics_history) == 1
        assert engine.metrics_history[0] == metrics
    
    def test_detect_bottlenecks_low_hit_rate(self):
        """Test bottleneck detection for low hit rate"""
        engine = OptimizationEngine()
        
        metrics = CacheMetrics(
            hit_rate=0.5,  # Below threshold
            miss_rate=0.5,
            avg_latency_ms=50.0,
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.05,
            timestamp=datetime.now()
        )
        
        bottlenecks = engine._detect_bottlenecks(metrics)
        
        assert len(bottlenecks) > 0
        assert any(b.component == "cache" for b in bottlenecks)
    
    def test_detect_bottlenecks_high_latency(self):
        """Test bottleneck detection for high latency"""
        engine = OptimizationEngine()
        
        metrics = CacheMetrics(
            hit_rate=0.9,
            miss_rate=0.1,
            avg_latency_ms=200.0,  # Above threshold
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.05,
            timestamp=datetime.now()
        )
        
        bottlenecks = engine._detect_bottlenecks(metrics)
        
        assert len(bottlenecks) > 0
        assert any(b.component == "api" for b in bottlenecks)
    
    @pytest.mark.asyncio
    async def test_generate_recommendations(self):
        """Test recommendation generation"""
        engine = OptimizationEngine()
        
        # Add some historical data
        for i in range(15):
            metrics = CacheMetrics(
                hit_rate=0.8 + i * 0.01,
                miss_rate=0.2 - i * 0.01,
                avg_latency_ms=50.0 + i,
                memory_usage_mb=500.0 + i * 10,
                throughput_qps=1000.0 + i * 100,
                eviction_rate=0.1,
                timestamp=datetime.now()
            )
            engine._store_metrics(metrics)
        
        # Train ML model
        engine.ml_predictor.train(engine.metrics_history)
        
        current_metrics = CacheMetrics(
            hit_rate=0.75,
            miss_rate=0.25,
            avg_latency_ms=80.0,
            memory_usage_mb=500.0,
            throughput_qps=2000.0,
            eviction_rate=0.15,
            timestamp=datetime.now()
        )
        
        recommendations = await engine._generate_recommendations(current_metrics)
        
        assert len(recommendations) > 0
        assert all(isinstance(r, OptimizationRecommendation) for r in recommendations)
    
    def test_generate_report(self):
        """Test report generation"""
        engine = OptimizationEngine()
        
        # Add some metrics
        for i in range(20):
            metrics = CacheMetrics(
                hit_rate=0.85 + i * 0.001,
                miss_rate=0.15 - i * 0.001,
                avg_latency_ms=50.0 + i,
                memory_usage_mb=500.0 + i * 10,
                throughput_qps=2000.0 + i * 50,
                eviction_rate=0.05,
                timestamp=datetime.now()
            )
            engine._store_metrics(metrics)
        
        report = engine.generate_report()
        
        assert 'generated_at' in report
        assert 'performance_summary' in report
        assert 'ml_model_status' in report
        assert 'system_health_score' in report
    
    def test_export_metrics(self, tmp_path):
        """Test metrics export"""
        engine = OptimizationEngine()
        
        # Add some metrics
        for i in range(10):
            metrics = CacheMetrics(
                hit_rate=0.85,
                miss_rate=0.15,
                avg_latency_ms=50.0,
                memory_usage_mb=500.0,
                throughput_qps=2000.0,
                eviction_rate=0.05,
                timestamp=datetime.now()
            )
            engine._store_metrics(metrics)
        
        # Export to temp file
        filepath = tmp_path / "test_metrics.json"
        result = engine.export_metrics(str(filepath))
        
        assert result == True
        assert filepath.exists()
        
        # Verify content
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        assert 'metrics' in data
        assert len(data['metrics']) == 10
    
    def test_calculate_health_score(self):
        """Test health score calculation"""
        engine = OptimizationEngine()
        
        # Good metrics
        good_metrics = [
            CacheMetrics(
                hit_rate=0.95,
                miss_rate=0.05,
                avg_latency_ms=20.0,
                memory_usage_mb=500.0,
                throughput_qps=3000.0,
                eviction_rate=0.02,
                timestamp=datetime.now()
            )
            for _ in range(10)
        ]
        
        score = engine._calculate_health_score(good_metrics)
        assert score >= 80
        
        # Poor metrics
        poor_metrics = [
            CacheMetrics(
                hit_rate=0.5,
                miss_rate=0.5,
                avg_latency_ms=200.0,
                memory_usage_mb=500.0,
                throughput_qps=500.0,
                eviction_rate=0.2,
                timestamp=datetime.now()
            )
            for _ in range(10)
        ]
        
        score = engine._calculate_health_score(poor_metrics)
        assert score < 60  # Adjusted threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
