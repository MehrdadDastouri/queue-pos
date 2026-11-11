import pytest
from queue_pos.models import CancellationModel, OrderQueueStatus, Side
from queue_pos.probability import FillProbabilityEstimator
from queue_pos.tracker import QueuePositionTracker


def test_queue_initial_placement():
    tracker = QueuePositionTracker()
    # Level currently has 50.0 resting lots; we place 10.0 lots
    order = tracker.track_order(
        order_id=1, side=Side.BID, price=100.0, quantity=10.0, current_level_volume=50.0
    )

    assert order.ahead_volume == 50.0
    assert order.behind_volume == 0.0
    assert order.remaining_quantity == 10.0
    assert order.total_level_volume == 60.0
    assert pytest.approx(order.relative_position, 0.001) == 50.0 / 60.0


def test_trade_depletion_and_partial_fill():
    tracker = QueuePositionTracker()
    order = tracker.track_order(
        order_id=1, side=Side.BID, price=100.0, quantity=10.0, current_level_volume=20.0
    )

    # 1. Trade prints 15.0 lots: eats ahead volume only
    fills = tracker.on_trade(price=100.0, side=Side.BID, volume=15.0)
    assert len(fills) == 0
    assert order.ahead_volume == 5.0
    assert order.status == OrderQueueStatus.PENDING

    # 2. Trade prints 8.0 lots: wipes remaining 5.0 ahead, fills 3.0 of our order
    fills = tracker.on_trade(price=100.0, side=Side.BID, volume=8.0)
    assert len(fills) == 1
    assert fills[0] == (1, 3.0)
    assert order.ahead_volume == 0.0
    assert order.remaining_quantity == 7.0
    assert order.status == OrderQueueStatus.PARTIALLY_FILLED


def test_proportional_cancellation_attrition():
    tracker = QueuePositionTracker(cancellation_model=CancellationModel.PROPORTIONAL)
    order = tracker.track_order(
        order_id=1, side=Side.ASK, price=200.0, quantity=10.0, current_level_volume=30.0
    )
    # Add 20.0 lots behind us
    tracker.on_level_volume_update(price=200.0, side=Side.ASK, new_total_volume=60.0)
    assert order.ahead_volume == 30.0
    assert order.behind_volume == 20.0

    # 10.0 lots cancelled at level: other volume is 50.0 (30 ahead, 20 behind)
    # Ahead cancels: 10 * (30/50) = 6.0 | Behind cancels: 10 * (20/50) = 4.0
    tracker.on_level_volume_update(price=200.0, side=Side.ASK, new_total_volume=50.0)
    assert pytest.approx(order.ahead_volume, 0.01) == 24.0
    assert pytest.approx(order.behind_volume, 0.01) == 16.0


def test_analytical_fill_probability_boundaries():
    # Immediate fill case: zero ahead volume
    prob_immediate = FillProbabilityEstimator.estimate_poisson_fill_prob(
        ahead_volume=0.0, order_quantity=5.0, trade_intensity=10.0, cancellation_intensity=2.0, horizon_sec=1.0
    )
    assert prob_immediate == 1.0

    # Deep queue with zero incoming flow: zero fill probability
    prob_dead = FillProbabilityEstimator.estimate_poisson_fill_prob(
        ahead_volume=100.0, order_quantity=10.0, trade_intensity=0.0, cancellation_intensity=0.0, horizon_sec=5.0
    )
    assert prob_dead == 0.0

    # Normal queue dynamics
    prob_active = FillProbabilityEstimator.estimate_poisson_fill_prob(
        ahead_volume=20.0, order_quantity=5.0, trade_intensity=15.0, cancellation_intensity=10.0, horizon_sec=2.0
    )
    assert 0.0 < prob_active < 1.0
