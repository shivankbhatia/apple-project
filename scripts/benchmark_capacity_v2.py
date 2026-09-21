from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Project setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from producer.kafka_producer import create_producer, normalize_click


STAGING_DIR = ROOT / "data" / "staging"

KAFKA_TOPIC = "clicks"
KAFKA_GROUP = "click-scorer-v1"

MONITOR_INTERVAL = 2.0
KAFKA_TIMEOUT = 5  # seconds to wait for Kafka commands


# ---------------------------------------------------------------------------
# Kafka operations with better error handling
# ---------------------------------------------------------------------------

def get_kafka_lag() -> int:
    """
    Return total consumer lag for the Flink consumer group.
    Returns -1 if Kafka is unreachable or consumer group metrics are unavailable.
    """
    cmd = [
        "docker",
        "exec",
        "kafka",
        "kafka-consumer-groups",
        "--bootstrap-server",
        "localhost:9092",
        "--describe",
        "--group",
        KAFKA_GROUP,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=KAFKA_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            return -1
    except (subprocess.TimeoutExpired, Exception):
        return -1

    lines = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    if not lines:
        return -1

    header_idx = -1
    lag_index = -1

    for idx, line in enumerate(lines):
        parts = line.split()
        if "LAG" in parts:
            header_idx = idx
            lag_index = parts.index("LAG")
            break

    if header_idx == -1 or lag_index == -1:
        return -1

    total = 0
    valid_partitions = 0

    for line in lines[header_idx + 1:]:
        parts = line.split()
        if len(parts) <= lag_index:
            continue

        lag_str = parts[lag_index]
        try:
            lag = int(lag_str)
            if lag >= 0:
                total += lag
                valid_partitions += 1
        except ValueError:
            continue

    if valid_partitions == 0 and total == 0:
        return 0 if header_idx != -1 else -1

    return total


# ---------------------------------------------------------------------------
# Docker resource usage
# ---------------------------------------------------------------------------

def parse_memory_mb(value: str) -> float:
    value = value.strip().upper()

    try:
        if value.endswith("GIB"):
            return float(value[:-3]) * 1024.0

        if value.endswith("MIB"):
            return float(value[:-3])

        if value.endswith("KIB"):
            return float(value[:-3]) / 1024.0

        if value.endswith("GB"):
            return float(value[:-2]) * 1000.0 / 1.048576

        if value.endswith("MB"):
            return float(value[:-2]) * 1000.0 / 1024.0

        if value.endswith("KB"):
            return float(value[:-2]) * 1000.0 / (1024.0 * 1024.0)

        if value.endswith("B"):
            return float(value[:-1]) / (1024.0 * 1024.0)

    except ValueError:
        pass

    return 0.0


def get_taskmanager_stats() -> tuple[float, float]:
    """
    Returns:
        CPU %
        RAM MB
    """
    cmd = [
        "docker",
        "stats",
        "--no-stream",
        "--format",
        "{{.CPUPerc}}\t{{.MemUsage}}",
        "flink-taskmanager",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=KAFKA_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            return 0.0, 0.0
    except (subprocess.TimeoutExpired, Exception):
        return 0.0, 0.0

    lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if not lines:
        return 0.0, 0.0

    line = lines[0]
    parts = line.split("\t")

    if len(parts) < 2:
        return 0.0, 0.0

    try:
        cpu = float(parts[0].replace("%", "").strip())
    except ValueError:
        cpu = 0.0

    memory = parts[1].split("/")[0].strip()
    ram_mb = parse_memory_mb(memory)

    return cpu, ram_mb


# ---------------------------------------------------------------------------
# Wait for Kafka to drain
# ---------------------------------------------------------------------------

def wait_for_kafka_drain(timeout: int = 60, initial_check_skip: bool = False) -> bool:
    """
    Wait for Kafka queue to drain.
    
    Args:
        timeout: Maximum seconds to wait
        initial_check_skip: If True, skip initial lag check and assume already started
    """

    print("Waiting for Kafka to drain...", end="", flush=True)

    start = time.monotonic()

    # First check - see if there's anything to drain
    if not initial_check_skip:
        initial_lag = get_kafka_lag()
        if initial_lag < 0:
            print(" (lag check unavailable, assuming drained)")
            return True
        if initial_lag == 0:
            print(" already drained.")
            time.sleep(2)
            return True

    while time.monotonic() - start < timeout:

        lag = get_kafka_lag()

        if lag == 0:
            print(" done.")
            time.sleep(2)
            return True

        if lag > 0:
            print(f"\n  Current lag: {lag:,}", end="", flush=True)

        print(".", end="", flush=True)
        time.sleep(2)

    final_lag = get_kafka_lag()
    print(f"\n  timeout. Remaining lag = {final_lag if final_lag >= 0 else 'UNKNOWN'}")

    return False


# ---------------------------------------------------------------------------
# Produce benchmark traffic
# ---------------------------------------------------------------------------

def produce_clicks(
    rate: int,
    duration: int,
    csv_path: Path,
    run_id: str,
) -> tuple[int, float]:

    producer = create_producer("localhost:9092")

    # Pre-load CSV rows into memory to eliminate Python disk I/O bottlenecks
    with csv_path.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))

    if not rows:
        producer.close()
        return 0, 0.0

    num_rows = len(rows)
    row_idx = 0
    sent = 0

    start = time.monotonic()
    end = start + duration

    # Pace messages smoothly in mini-batches (20 slices/sec) to avoid burst spikes
    slices_per_sec = 20
    slice_interval = 1.0 / slices_per_sec
    items_per_slice = max(1, int(round(rate / slices_per_sec)))

    slice_count = 0

    while True:
        if time.monotonic() >= end:
            break

        for _ in range(items_per_slice):
            if time.monotonic() >= end:
                break

            row = rows[row_idx % num_rows]
            row_idx += 1

            event = normalize_click(row)

            # Benchmark metadata
            event["benchmark_run_id"] = run_id
            event["benchmark_send_ns"] = time.time_ns()

            producer.send(
                KAFKA_TOPIC,
                key=event["ip"],
                value=event,
            )

            sent += 1

        slice_count += 1
        next_target = start + (slice_count * slice_interval)
        sleep_needed = next_target - time.monotonic()

        if sleep_needed > 0:
            time.sleep(sleep_needed)

    producer.flush()
    producer.close()

    elapsed = time.monotonic() - start

    return sent, elapsed


# ---------------------------------------------------------------------------
# Read Flink benchmark outputs
# ---------------------------------------------------------------------------

def get_benchmark_results(
    run_id: str,
) -> tuple[list[float], int]:

    latencies = []
    processed = 0

    if not STAGING_DIR.exists():
        print(f"  Warning: Staging directory not found: {STAGING_DIR}")
        return latencies, processed

    for file_path in STAGING_DIR.rglob("*.json"):

        if file_path.name.startswith("."):
            continue

        try:
            # Use file modification time as fallback timestamp for records missing benchmark_output_ns
            file_mtime_ns = file_path.stat().st_mtime_ns

            with file_path.open(encoding="utf-8") as file:

                for line in file:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("benchmark_run_id") != run_id:
                        continue

                    processed += 1

                    send_ns = data.get("benchmark_send_ns")

                    if send_ns is None:
                        continue

                    output_ns = data.get("benchmark_output_ns")

                    # If Flink does not provide an explicit output timestamp,
                    # fall back to the file modification time when Flink wrote the record.
                    if output_ns is None:
                        output_ns = file_mtime_ns

                    try:
                        send_ns = int(send_ns)
                        output_ns = int(output_ns)
                    except (TypeError, ValueError):
                        continue

                    latency_ms = (output_ns - send_ns) / 1_000_000

                    if 0 <= latency_ms < 86_400_000:
                        latencies.append(latency_ms)

        except (OSError, UnicodeDecodeError):
            continue

    return latencies, processed


# ---------------------------------------------------------------------------
# Single benchmark
# ---------------------------------------------------------------------------

def run_test(
    rate: int,
    duration: int,
    csv_path: Path,
    skip_initial_drain: bool = False,
) -> dict:

    run_id = (
        f"benchmark-{rate}-"
        f"{uuid.uuid4().hex[:8]}"
    )

    print()
    print("=" * 65)
    print(f"TESTING {rate:,} CLICKS/SEC")
    print("=" * 65)

    # Clean starting state
    if not wait_for_kafka_drain(timeout=60, initial_check_skip=skip_initial_drain):
        return {
            "rate": rate,
            "status": "INVALID",
            "error": "Kafka drain timeout",
        }

    # Monitoring setup
    monitor = []
    stop_monitor = threading.Event()
    test_start = time.monotonic()

    def monitor_system():
        while not stop_monitor.is_set():
            elapsed = time.monotonic() - test_start
            lag = get_kafka_lag()
            cpu, ram = get_taskmanager_stats()

            monitor.append(
                {
                    "time": elapsed,
                    "lag": lag,
                    "cpu": cpu,
                    "ram": ram,
                }
            )

            stop_monitor.wait(MONITOR_INTERVAL)

    thread = threading.Thread(
        target=monitor_system,
        daemon=True,
    )
    thread.start()

    # Produce workload
    print(f"Producing {rate:,} clicks/sec for {duration} seconds...")
    sent, producer_time = produce_clicks(
        rate=rate,
        duration=duration,
        csv_path=csv_path,
        run_id=run_id,
    )

    print(f"Sent {sent:,} events in {producer_time:.2f}s")

    # Wait for Flink to finish while keeping monitoring ACTIVE during drain
    drain_start = time.monotonic()
    drained = wait_for_kafka_drain(timeout=120)
    drain_time = time.monotonic() - drain_start
    total_time = time.monotonic() - test_start

    # Stop monitor after drain phase completes
    stop_monitor.set()
    thread.join(timeout=5)

    # Read Flink results
    print("Reading benchmark results...")
    latencies, processed = get_benchmark_results(run_id)

    # Calculate metrics
    actual_ingestion_rate = (
        sent / producer_time
        if producer_time > 0
        else 0
    )

    processing_rate = (
        processed / total_time
        if total_time > 0
        else 0
    )

    throughput_ratio = (
        processing_rate / actual_ingestion_rate
        if actual_ingestion_rate > 0
        else 0
    )

    if latencies:
        p50 = float(np.percentile(latencies, 50))
        p95 = float(np.percentile(latencies, 95))
        p99 = float(np.percentile(latencies, 99))
        max_latency = max(latencies)
    else:
        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        max_latency = 0.0

    # Lag & Resource Metrics
    valid_lags = [x["lag"] for x in monitor if x["lag"] >= 0]
    if valid_lags:
        max_lag = max(valid_lags)
        final_test_lag = valid_lags[-1]

        increasing = sum(
            current > previous
            for previous, current
            in zip(valid_lags, valid_lags[1:])
        )
        comparisons = max(1, len(valid_lags) - 1)
        lag_growth_fraction = increasing / comparisons
    else:
        max_lag = 0
        final_test_lag = 0
        lag_growth_fraction = 0.0

    cpu_vals = [x["cpu"] for x in monitor]
    avg_cpu = float(np.mean(cpu_vals)) if cpu_vals else 0.0
    max_cpu = max(cpu_vals) if cpu_vals else 0.0

    ram_vals = [x["ram"] for x in monitor]
    avg_ram = float(np.mean(ram_vals)) if ram_vals else 0.0
    max_ram = max(ram_vals) if ram_vals else 0.0

    raw_final_lag = get_kafka_lag()
    final_lag = max(0, raw_final_lag) if raw_final_lag >= 0 else 0

    # Determine stability
    throughput_ok = throughput_ratio >= 0.90
    lag_ok = final_lag <= max(100, sent * 0.01)
    sustained_lag_growth = (
        lag_growth_fraction >= 0.70
        and final_test_lag > 1000
    )
    latency_available = len(latencies) > 0

    if not latency_available:
        status = "INVALID"
    elif not drained:
        status = "SATURATED"
    elif not throughput_ok:
        status = "SATURATED"
    elif not lag_ok:
        status = "SATURATED"
    elif sustained_lag_growth:
        status = "SATURATED"
    else:
        status = "STABLE"

    # Print results
    print()
    print(f"Target rate:          {rate:,} clicks/sec")
    print(f"Actual ingestion:     {actual_ingestion_rate:,.1f} clicks/sec")
    print(f"Processed throughput: {processing_rate:,.1f} clicks/sec")

    print()
    print(f"p50 latency:          {p50:,.1f} ms")
    print(f"p95 latency:          {p95:,.1f} ms")
    print(f"p99 latency:          {p99:,.1f} ms")
    print(f"Max latency:          {max_latency:,.1f} ms")

    print()
    print(f"Maximum Kafka lag:    {max_lag:,}")
    print(f"Final Kafka lag:      {final_lag:,}")
    print(f"Kafka drain time:     {drain_time:,.1f} sec")

    print()
    print(f"TaskManager avg CPU:  {avg_cpu:.1f}%")
    print(f"TaskManager max CPU:  {max_cpu:.1f}%")
    print(f"TaskManager avg RAM:  {avg_ram:,.1f} MB")
    print(f"TaskManager max RAM:  {max_ram:,.1f} MB")

    print()
    print(f"Throughput ratio:     {throughput_ratio:.2%}")
    print(f"Latency samples:      {len(latencies):,}")
    print(f"Processed records:    {processed:,}")

    print()
    print(f"RESULT:               {status}")

    return {
        "rate": rate,
        "actual_ingestion": actual_ingestion_rate,
        "processed_rate": processing_rate,
        "throughput_ratio": throughput_ratio,
        "p50": p50,
        "p95": p95,
        "p99": p99,
        "max_latency": max_latency,
        "max_lag": max_lag,
        "final_lag": final_lag,
        "drain_time": drain_time,
        "cpu_avg": avg_cpu,
        "cpu_max": max_cpu,
        "ram_avg": avg_ram,
        "ram_max": max_ram,
        "processed": processed,
        "latency_samples": len(latencies),
        "status": status,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Find the operating limit of the PyFlink ad-fraud speed layer."
    )

    parser.add_argument(
        "--rates",
        nargs="+",
        type=int,
        default=[100, 250, 500, 1000, 2000, 5000, 10000],
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration per test in seconds",
    )

    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "data" / "clicks_sample.csv",
    )

    parser.add_argument(
        "--skip-first-drain",
        action="store_true",
        help="Skip the initial drain check (useful when resuming benchmarks)",
    )

    args = parser.parse_args()

    if not args.csv.exists():
        raise FileNotFoundError(f"Dataset not found: {args.csv}")

    results = []

    print()
    print("=" * 65)
    print("PYFLINK SPEED-LAYER CAPACITY TEST")
    print("=" * 65)
    print(f"Duration per test: {args.duration} seconds")
    print(f"Rates: {', '.join(map(str, sorted(args.rates)))}")
    print("=" * 65)

    for idx, rate in enumerate(sorted(set(args.rates))):

        result = run_test(
            rate=rate,
            duration=args.duration,
            csv_path=args.csv,
            skip_initial_drain=args.skip_first_drain and idx == 0,
        )

        results.append(result)

        if result["status"] == "INVALID":
            print("\nBenchmark stopped because latency could not be measured.")
            break

        if result["status"] == "SATURATED":
            print()
            print(f"*** SATURATION DETECTED AROUND {rate:,} clicks/sec ***")
            print("Run a finer-grained test around this rate to determine the boundary.")
            break

    # Final summary
    stable = [r for r in results if r["status"] == "STABLE"]
    saturated = [r for r in results if r["status"] == "SATURATED"]

    print()
    print("=" * 65)
    print("FINAL CAPACITY SUMMARY")
    print("=" * 65)

    if stable:
        best = max(stable, key=lambda x: x["rate"])

        print(f"Maximum tested stable rate: {best['rate']:,} clicks/sec")
        print(
            f"Latency at this rate: "
            f"p50={best['p50']:.1f} ms, "
            f"p95={best['p95']:.1f} ms, "
            f"p99={best['p99']:.1f} ms"
        )
        print(f"Processed throughput: {best['processed_rate']:.1f} clicks/sec")

    if saturated:
        first_saturated = min(saturated, key=lambda x: x["rate"])
        print(f"First observed saturation: {first_saturated['rate']:,} clicks/sec")

    if stable and saturated:
        print()
        print(
            f"Operating boundary: "
            f"{best['rate']:,}–{first_saturated['rate']:,} clicks/sec"
        )
    elif stable:
        print()
        print("No saturation was observed within the tested range.")

    print("=" * 65)

    # Save results to CSV
    output_file = ROOT / "benchmark_results.csv"
    if results:
        import csv as csv_module
        with output_file.open('w', newline='') as f:
            writer = csv_module.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    main()
