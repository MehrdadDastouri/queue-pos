"""High-resolution latency benchmarking harness for queue position tracking."""

import gc
import statistics
import time
from typing import List
from queue_pos.models import CancellationModel, Side
from queue_pos.tracker import QueuePositionTracker


def run_benchmark(num_events: int = 200_000) -> None:
    tracker = QueuePositionTracker(cancellation_model=CancellationModel.PROPORTIONAL)
    price = 100.0

    # Place a resting order in a deep queue
    tracker.track_order(
        order_id=1,
        side=Side.BID,
        price=price,
        quantity=50.0,
        current_level_volume=500_000.0,
    )

    latencies_ns: List[int] = [0] * num_events

    print(f"[*] Benchmarking {num_events:,} queue updates (trades + level deltas)...")
    print("[*] Disabling GC for deterministic sub-microsecond profiling...")

    gc.disable()
    start_wall = time.perf_counter_ns()

    for i in range(num_events):
        t0 = time.perf_counter_ns()
        if i % 2 == 0:
            tracker.on_trade(price=price, side=Side.BID, volume=1.5)
        else:
            tracker.on_level_volume_update(price=price, side=Side.BID, new_total_volume=499_000.0 - (i * 0.5))
        t1 = time.perf_counter_ns()
        latencies_ns[i] = t1 - t0

    end_wall = time.perf_counter_ns()
    gc.enable()

    total_duration_sec = (end_wall - start_wall) / 1e9
    throughput = num_events / total_duration_sec

    latencies_ns.sort()
    p50 = latencies_ns[int(num_events * 0.50)]
    p90 = latencies_ns[int(num_events * 0.90)]
    p99 = latencies_ns[int(num_events * 0.99)]
    p99_9 = latencies_ns[int(num_events * 0.999)]
    mean_lat = statistics.mean(latencies_ns)

    print("\n" + "=" * 55)
    print("           QUEUE-POS BENCHMARK RESULTS")
    print("=" * 55)
    print(f"Processed Events         : {num_events:,}")
    print(f"Total Duration           : {total_duration_sec:.4f} sec")
    print(f"Throughput               : {throughput:,.0f} updates/sec")
    print("-" * 55)
    print(f"Mean Latency             : {mean_lat / 1000.0:.2f} µs ({mean_lat:.0f} ns)")
    print(f"P50 Latency (Median)     : {p50 / 1000.0:.2f} µs ({p50:.0f} ns)")
    print(f"P90 Latency              : {p90 / 1000.0:.2f} µs ({p90:.0f} ns)")
    print(f"P99 Latency              : {p99 / 1000.0:.2f} µs ({p99:.0f} ns)")
    print(f"P99.9 Latency (Tail)     : {p99_9 / 1000.0:.2f} µs ({p99_9:.0f} ns)")
    print("=" * 55)


if __name__ == "__main__":
    run_benchmark(num_events=200_000)
