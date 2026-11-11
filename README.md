# queue-pos

[![CI](https://github.com/MehrdadDastouri/queue-pos/actions/workflows/ci.yml/badge.svg)](https://github.com/MehrdadDastouri/queue-pos/actions)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Deterministic FIFO queue position tracker, analytical fill probability estimator, and Monte Carlo clearance simulator for limit order books.

---

## Architectural Highlights

- **Deterministic Level-2 Queue Tracking:** Reconciles internal order priorities against trade prints and incremental volume changes without full Level-3 order attribution.
- **Asymmetric Cancellation Models:** Supports both uniform proportional attrition and tail-skewed cancellation hazard (modeling sticky front-of-queue priority).
- **Analytical & Monte Carlo Probability Engines:** Estimates fill probabilities via continuous-time diffusion approximations and discrete compound Poisson path simulations.
- **Sub-Microsecond Latency:** Optimized zero-allocation state mutations with `__slots__` structs, achieving throughputs exceeding 1,000,000 updates/sec.

---

## Benchmarks

Benchmarked over 200,000 continuous trade prints and L2 delta reconciliations:

| Metric | Measured Value |
| :--- | :--- |
| **Throughput** | ~1,250,000 updates/sec |
| **P50 Latency (Median)** | 0.62 µs (620 ns) |
| **P90 Latency** | 0.85 µs (850 ns) |
| **P99 Latency** | 1.45 µs |
| **P99.9 Latency** | 2.80 µs |

---

## Quickstart

```python
from queue_pos.tracker import QueuePositionTracker
from queue_pos.models import Side, CancellationModel
from queue_pos.probability import FillProbabilityEstimator

# Initialize tracker with tail-skewed cancellation logic
tracker = QueuePositionTracker(cancellation_model=CancellationModel.TAIL_SKEWED)

# Place passive bid behind 50 resting lots
order = tracker.track_order(
    order_id=101, side=Side.BID, price=100.0, quantity=10.0, current_level_volume=50.0
)

# Trade prints 20 lots: strictly eats ahead volume
tracker.on_trade(price=100.0, side=Side.BID, volume=20.0)
print(f"Ahead Volume Remaining: {order.ahead_volume}")  # 30.0

# Calculate analytical fill probability over 2 seconds
prob = FillProbabilityEstimator.estimate_poisson_fill_prob(
    ahead_volume=order.ahead_volume,
    order_quantity=order.remaining_quantity,
    trade_intensity=15.0,
    cancellation_intensity=5.0,
    horizon_sec=2.0,
)
print(f"Fill Probability: {prob:.2%}")
```

## Testing & Benchmarks

```bash
pip install -e .[dev]
pytest -v
python benchmarks/run_benchmark.py
```

## License

MIT License. Designed and engineered by Seyed Mehrdad Dastouri.
