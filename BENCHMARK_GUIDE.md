# Fraud Detection System Benchmarking Guide

## Overview

This guide explains the benchmarking scripts for testing the fraud detection system performance across different components.

## Available Benchmarks

### 1. Standalone Benchmarks (`scripts/benchmark_standalone.py`)

The **recommended approach** for system performance testing. This script independently benchmarks each component without requiring the full Flink infrastructure.

#### Features:
- **Kafka Producer Throughput**: Tests event production rate
- **Feature Extraction Performance**: Measures feature engineering latency
- **Model Inference Performance**: Tests ML model inference speed
- **No Flink dependency**: Works without needing the full streaming pipeline

#### Usage:

```bash
# Run all benchmarks with 10,000 events
python scripts/benchmark_standalone.py --num-events 10000

# Run specific benchmark
python scripts/benchmark_standalone.py --benchmark features --num-events 5000

# Save results to JSON
python scripts/benchmark_standalone.py --num-events 10000 --output results.json

# Use custom data file
python scripts/benchmark_standalone.py --csv data/custom_clicks.csv --num-events 5000
```

#### Output:

```
BENCHMARK 1: KAFKA PRODUCER THROUGHPUT
  Events sent:    10,000
  Throughput:     4,793 events/sec

BENCHMARK 2: FEATURE EXTRACTION PERFORMANCE
  Latency (ms):
    Average:      0.012
    p50:          0.008
    p95:          0.011
    p99:          0.018

BENCHMARK 3: MODEL INFERENCE PERFORMANCE
  Latency (ms):
    Average:      0.148
    p50:          0.137
    p95:          0.156
    p99:          0.407
```

#### Interpreting Results:

| Metric | Component | Target | Status |
|--------|-----------|--------|--------|
| Throughput | Kafka Producer | > 1,000 events/sec | ✓ PASS |
| Throughput | Features | > 50,000 events/sec | ✓ PASS |
| Throughput | Inference | > 1,000 events/sec | ✓ PASS |
| p99 Latency | Features | < 1ms | ✓ PASS |
| p99 Latency | Inference | < 1ms | ✓ PASS |

---

### 2. Capacity Benchmark (`scripts/benchmark_capacity.py`)

Tests end-to-end system performance under load with increasing throughput rates.

#### Features:
- Progressive rate testing (100, 250, 500, 1000, 2000, 5000, 10000 events/sec)
- Monitors Kafka lag, CPU, and memory usage
- Determines saturation point
- Requires full Docker stack (Kafka, Flink, etc.)

#### Prerequisites:

```bash
# Ensure Docker services are running
docker-compose up -d

# Verify Flink job is deployed and Python is available in container
```

#### Usage:

```bash
# Run with default rates
python scripts/benchmark_capacity.py

# Test specific rates
python scripts/benchmark_capacity.py --rates 100 500 1000

# Set test duration
python scripts/benchmark_capacity.py --duration 60 --rates 1000

# Skip initial drain check (for resuming tests)
python scripts/benchmark_capacity.py --skip-first-drain
```

#### Known Issues:

**Issue**: Flink job fails with "Cannot run program \"python\": error=2"

**Root Cause**: Flink container doesn't have Python 3.10 configured for PyFlink.

**Solution**: 
1. Install Python in Flink container, or
2. Use the standalone benchmark script instead (recommended)

---

## Performance Targets

Based on system architecture and current implementation:

### Component Targets

| Component | Target Throughput | Target Latency | Notes |
|-----------|-------------------|-----------------|-------|
| Kafka Producer | > 5,000 events/sec | - | Network I/O bound |
| Feature Extraction | > 80,000 events/sec | p99 < 1ms | In-memory operations |
| Model Inference | > 6,000 events/sec | p99 < 1ms | CPU bound |

### System Integration Targets

| Metric | Target | Current |
|--------|--------|---------|
| End-to-end latency (p99) | < 100ms | TBD |
| System throughput | > 1,000 events/sec | TBD |
| Kafka lag at 1000 events/sec | < 100 | Monitor |
| CPU utilization | < 80% | Monitor |
| Memory utilization | < 70% | Monitor |

---

## Running Comprehensive Benchmarks

### Quick Test (5-10 minutes)

```bash
python scripts/benchmark_standalone.py --num-events 5000 --output quick_test.json
```

### Standard Test (20-30 minutes)

```bash
python scripts/benchmark_standalone.py --num-events 50000 --output standard_test.json
```

### Full Capacity Test (45-60 minutes)

Requires full Docker setup:

```bash
# Start services
docker-compose up -d

# Wait for Kafka and Flink to be ready
sleep 30

# Run capacity test
python scripts/benchmark_capacity.py --duration 120 --rates 100 500 1000 2000

# Analyze results
cat benchmark_results.csv
```

---

## Analyzing Results

### Output Format

Results are saved to `benchmark_results.csv` with the following columns:

```csv
benchmark,num_events,sent/processed/inferred,errors,elapsed,throughput,latency_p50,latency_p95,latency_p99,latency_avg,latency_max,status
```

### Example Analysis

```python
import pandas as pd

df = pd.read_csv('benchmark_results.csv')

# Check throughput
print(df[['benchmark', 'throughput']].to_string())

# Check error rates
print(df[['benchmark', 'errors']].to_string())

# Check latency distribution
print(df[['benchmark', 'latency_p50', 'latency_p95', 'latency_p99']].to_string())
```

### Performance Issues

**High Latency in Feature Extraction**
- Check CPU usage
- Profile with `cProfile`
- Consider caching campaign/publisher stats

**High Error Rate**
- Check data format
- Verify model features match FEATURE_ORDER
- Check memory availability

**Low Throughput**
- Kafka broker performance
- Network bandwidth
- Serialization overhead

---

## Comparing Results

### Version Comparison

```bash
# Run baseline
python scripts/benchmark_standalone.py --num-events 50000 --output baseline.json

# Make changes...

# Run comparison
python scripts/benchmark_standalone.py --num-events 50000 --output optimized.json

# Compare
python -c "
import json
with open('baseline.json') as f:
    baseline = json.load(f)
with open('optimized.json') as f:
    optimized = json.load(f)
    
for b, o in zip(baseline, optimized):
    name = b['benchmark']
    throughput_improvement = (o['throughput'] - b['throughput']) / b['throughput'] * 100
    latency_improvement = (b['latency_avg'] - o['latency_avg']) / b['latency_avg'] * 100
    print(f\"{name}: {throughput_improvement:+.1f}% throughput, {latency_improvement:+.1f}% latency\")
"
```

---

## Troubleshooting

### Script Fails to Start

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Verify dependencies
pip install -r requirements.txt

# Check data file exists
ls -lh data/clicks_sample.csv
```

### Out of Memory

```bash
# Reduce event count
python scripts/benchmark_standalone.py --num-events 1000

# Run individually
python scripts/benchmark_standalone.py --benchmark producer --num-events 10000
```

### Kafka Connection Errors

```bash
# Check Docker containers
docker ps

# Verify Kafka is accessible
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092
```

### Model Loading Errors

```bash
# Verify model file exists
ls -lh models/click_fraud_model.pkl

# Verify feature list exists
ls -lh models/feature_list.pkl

# Verify campaign stats exist
ls -lh models/campaign_stats.json
```

---

## Next Steps

1. **Baseline**: Run the standalone benchmark and save results as baseline
2. **Optimize**: Identify bottlenecks from performance metrics
3. **Profile**: Use Python profilers to dig deeper into hot paths
4. **Compare**: Run benchmarks again after optimizations
5. **Monitor**: Set up continuous performance monitoring

---

## References

- [Kafka Python Client](https://kafka-python.readthedocs.io/)
- [scikit-learn Performance Tips](https://scikit-learn.org/stable/)
- [NumPy Performance Guide](https://numpy.org/doc/stable/user/basics.broadcasting.html)
