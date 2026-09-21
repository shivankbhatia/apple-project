"""
Standalone benchmarking script for the fraud detection system.

This script can be run independently to test:
1. Kafka producer throughput
2. Model inference latency
3. Feature extraction performance
4. System resource utilization
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from producer.kafka_producer import create_producer, normalize_click
from features.click_features import enrich_ordered_records, IncrementalClickFeatures, FEATURE_ORDER, vectorize
import pickle
import json as json_module


# ---------------------------------------------------------------------------
# Benchmark 1: Kafka Producer Throughput
# ---------------------------------------------------------------------------

def benchmark_kafka_producer(
    num_events: int = 10000,
    csv_path: Path | None = None,
) -> dict:
    """
    Benchmark the Kafka producer throughput.
    
    Args:
        num_events: Number of events to produce
        csv_path: Path to CSV data source
        
    Returns:
        Dictionary with throughput metrics
    """
    
    if csv_path is None:
        csv_path = ROOT / "data" / "clicks_sample.csv"
    
    print()
    print("=" * 65)
    print("BENCHMARK 1: KAFKA PRODUCER THROUGHPUT")
    print("=" * 65)
    print(f"Target events: {num_events:,}")
    
    # Load CSV data
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    
    if not rows:
        print("ERROR: No data in CSV file")
        return {"status": "FAILED", "error": "No data"}
    
    producer = create_producer("localhost:9092")
    
    start = time.monotonic()
    sent = 0
    errors = 0
    
    try:
        for i in range(num_events):
            row = rows[i % len(rows)]
            event = normalize_click(row)
            
            try:
                producer.send(
                    "clicks",
                    key=event["ip"],
                    value=event,
                )
                sent += 1
            except Exception as e:
                errors += 1
                if errors <= 5:  # Log first 5 errors
                    print(f"  Error sending event {i}: {e}")
            
            if (i + 1) % 1000 == 0:
                print(f"  Sent {i + 1:,} events...")
    
    finally:
        producer.flush()
        producer.close()
    
    elapsed = time.monotonic() - start
    throughput = sent / elapsed if elapsed > 0 else 0
    
    print()
    print(f"Events sent:    {sent:,}")
    print(f"Events failed:  {errors:,}")
    print(f"Elapsed time:   {elapsed:.2f}s")
    print(f"Throughput:     {throughput:,.0f} events/sec")
    
    return {
        "benchmark": "kafka_producer",
        "num_events": num_events,
        "sent": sent,
        "errors": errors,
        "elapsed": elapsed,
        "throughput": throughput,
        "status": "SUCCESS" if sent > 0 else "FAILED",
    }


# ---------------------------------------------------------------------------
# Benchmark 2: Feature Extraction Performance
# ---------------------------------------------------------------------------

def benchmark_feature_extraction(
    num_events: int = 10000,
    csv_path: Path | None = None,
) -> dict:
    """
    Benchmark feature extraction from click events.
    """
    
    if csv_path is None:
        csv_path = ROOT / "data" / "clicks_sample.csv"
    
    print()
    print("=" * 65)
    print("BENCHMARK 2: FEATURE EXTRACTION PERFORMANCE")
    print("=" * 65)
    print(f"Target events: {num_events:,}")
    
    # Load CSV data
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    
    if not rows:
        print("ERROR: No data in CSV file")
        return {"status": "FAILED", "error": "No data"}
    
    # Load campaign and publisher stats
    campaign_stats_path = ROOT / "models" / "campaign_stats.json"
    campaign_stats = {}
    if campaign_stats_path.exists():
        with campaign_stats_path.open() as f:
            campaign_stats = json_module.load(f)
    
    # Initialize feature engine
    engine = IncrementalClickFeatures(campaign_stats=campaign_stats)
    
    latencies = []
    errors = 0
    
    start = time.monotonic()
    
    try:
        for i in range(num_events):
            row = rows[i % len(rows)]
            
            try:
                event_start = time.perf_counter()
                # Normalize click first (add required fields)
                normalized = normalize_click(row)
                # Extract features
                features = engine.enrich(normalized)
                event_time = (time.perf_counter() - event_start) * 1000  # ms
                latencies.append(event_time)
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error processing event {i}: {e}")
            
            if (i + 1) % 1000 == 0:
                print(f"  Processed {i + 1:,} events...")
    
    finally:
        elapsed = time.monotonic() - start
    
    if latencies:
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        avg_lat = np.mean(latencies)
        max_lat = np.max(latencies)
        throughput = len(latencies) / elapsed if elapsed > 0 else 0
    else:
        p50 = p95 = p99 = avg_lat = max_lat = throughput = 0.0
    
    print()
    print(f"Events processed: {len(latencies):,}")
    print(f"Events failed:    {errors:,}")
    print(f"Elapsed time:     {elapsed:.2f}s")
    print(f"Throughput:       {throughput:,.0f} events/sec")
    print()
    print(f"Latency (ms):")
    print(f"  Average:        {avg_lat:.3f}")
    print(f"  p50:            {p50:.3f}")
    print(f"  p95:            {p95:.3f}")
    print(f"  p99:            {p99:.3f}")
    print(f"  Max:            {max_lat:.3f}")
    
    return {
        "benchmark": "feature_extraction",
        "num_events": num_events,
        "processed": len(latencies),
        "errors": errors,
        "elapsed": elapsed,
        "throughput": throughput,
        "latency_p50": float(p50),
        "latency_p95": float(p95),
        "latency_p99": float(p99),
        "latency_avg": float(avg_lat),
        "latency_max": float(max_lat),
        "status": "SUCCESS" if len(latencies) > 0 else "FAILED",
    }


# ---------------------------------------------------------------------------
# Benchmark 3: Model Inference
# ---------------------------------------------------------------------------

def benchmark_model_inference(
    num_events: int = 10000,
    csv_path: Path | None = None,
) -> dict:
    """
    Benchmark fraud detection model inference latency.
    """
    
    if csv_path is None:
        csv_path = ROOT / "data" / "clicks_sample.csv"
    
    print()
    print("=" * 65)
    print("BENCHMARK 3: MODEL INFERENCE PERFORMANCE")
    print("=" * 65)
    print(f"Target events: {num_events:,}")
    
    # Load model
    model_path = ROOT / "models" / "click_fraud_model.pkl"
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        return {"status": "FAILED", "error": "Model not found"}
    
    try:
        with model_path.open('rb') as f:
            model = pickle.load(f)
        print(f"Model loaded successfully")
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        return {"status": "FAILED", "error": str(e)}
    
    # Load CSV data
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    
    if not rows:
        print("ERROR: No data in CSV file")
        return {"status": "FAILED", "error": "No data"}
    
    # Load campaign stats for feature extraction
    campaign_stats_path = ROOT / "models" / "campaign_stats.json"
    campaign_stats = {}
    if campaign_stats_path.exists():
        with campaign_stats_path.open() as f:
            campaign_stats = json_module.load(f)
    
    # Initialize feature engine
    engine = IncrementalClickFeatures(campaign_stats=campaign_stats)
    
    latencies = []
    errors = 0
    predictions = {"fraud": 0, "legitimate": 0}
    
    start = time.monotonic()
    
    try:
        for i in range(num_events):
            row = rows[i % len(rows)]
            
            try:
                # Normalize and extract features
                normalized = normalize_click(row)
                features_dict = engine.enrich(normalized)
                
                # Vectorize features in the exact order expected by model
                feature_vector = vectorize(features_dict)
                
                # Run inference
                infer_start = time.perf_counter()
                prediction = model.predict([feature_vector])[0]
                infer_time = (time.perf_counter() - infer_start) * 1000  # ms
                
                latencies.append(infer_time)
                predictions["fraud" if prediction == 1 else "legitimate"] += 1
                
            except Exception as e:
                errors += 1
                if errors <= 5:
                    print(f"  Error inferring event {i}: {e}")
            
            if (i + 1) % 1000 == 0:
                print(f"  Inferred {i + 1:,} events...")
    
    finally:
        elapsed = time.monotonic() - start
    
    if latencies:
        p50 = np.percentile(latencies, 50)
        p95 = np.percentile(latencies, 95)
        p99 = np.percentile(latencies, 99)
        avg_lat = np.mean(latencies)
        max_lat = np.max(latencies)
        throughput = len(latencies) / elapsed if elapsed > 0 else 0
    else:
        p50 = p95 = p99 = avg_lat = max_lat = throughput = 0.0
    
    print()
    print(f"Events inferred:  {len(latencies):,}")
    print(f"Events failed:    {errors:,}")
    print(f"Elapsed time:     {elapsed:.2f}s")
    print(f"Throughput:       {throughput:,.0f} events/sec")
    print()
    print(f"Predictions:")
    print(f"  Fraud:          {predictions['fraud']:,}")
    print(f"  Legitimate:     {predictions['legitimate']:,}")
    print()
    print(f"Latency (ms):")
    print(f"  Average:        {avg_lat:.3f}")
    print(f"  p50:            {p50:.3f}")
    print(f"  p95:            {p95:.3f}")
    print(f"  p99:            {p99:.3f}")
    print(f"  Max:            {max_lat:.3f}")
    
    return {
        "benchmark": "model_inference",
        "num_events": num_events,
        "inferred": len(latencies),
        "errors": errors,
        "elapsed": elapsed,
        "throughput": throughput,
        "fraud_count": predictions["fraud"],
        "legitimate_count": predictions["legitimate"],
        "latency_p50": float(p50),
        "latency_p95": float(p95),
        "latency_p99": float(p99),
        "latency_avg": float(avg_lat),
        "latency_max": float(max_lat),
        "status": "SUCCESS" if len(latencies) > 0 else "FAILED",
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    
    parser = argparse.ArgumentParser(
        description="Benchmark fraud detection system components"
    )
    
    parser.add_argument(
        "--benchmark",
        choices=["all", "producer", "features", "inference"],
        default="all",
        help="Which benchmark to run",
    )
    
    parser.add_argument(
        "--num-events",
        type=int,
        default=10000,
        help="Number of events to process",
    )
    
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data" / "clicks_sample.csv",
        help="Path to CSV data",
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to save results as JSON",
    )
    
    args = parser.parse_args()
    
    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        sys.exit(1)
    
    results = []
    
    print()
    print("=" * 65)
    print("FRAUD DETECTION SYSTEM BENCHMARK SUITE")
    print("=" * 65)
    print(f"CSV data: {args.csv}")
    print(f"Events per benchmark: {args.num_events:,}")
    print("=" * 65)
    
    try:
        if args.benchmark in ["all", "producer"]:
            result = benchmark_kafka_producer(args.num_events, args.csv)
            results.append(result)
        
        if args.benchmark in ["all", "features"]:
            result = benchmark_feature_extraction(args.num_events, args.csv)
            results.append(result)
        
        if args.benchmark in ["all", "inference"]:
            result = benchmark_model_inference(args.num_events, args.csv)
            results.append(result)
    
    except KeyboardInterrupt:
        print("\n\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nBenchmark failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Summary
    print()
    print("=" * 65)
    print("BENCHMARK SUMMARY")
    print("=" * 65)
    
    for result in results:
        status = result.get("status", "UNKNOWN")
        benchmark = result.get("benchmark", "unknown")
        throughput = result.get("throughput", 0)
        
        print(f"\n{benchmark.upper()}: {status}")
        if throughput > 0:
            print(f"  Throughput: {throughput:,.0f} events/sec")
    
    # Save results
    if args.output:
        with args.output.open('w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
