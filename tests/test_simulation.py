import numpy as np
from queue_pos.models import CancellationModel
from queue_pos.probability import FillProbabilityEstimator
from queue_pos.simulator import QueueMonteCarloSimulator


def test_monte_carlo_convergence_to_analytical_bound():
    ahead_vol = 30.0
    order_qty = 5.0
    horizon = 2.0
    trade_rate = 20.0
    cancel_rate = 10.0

    # 1. Analytical approximation
    prob_analytical = FillProbabilityEstimator.estimate_poisson_fill_prob(
        ahead_volume=ahead_vol,
        order_quantity=order_qty,
        trade_intensity=trade_rate,
        cancellation_intensity=cancel_rate,
        horizon_sec=horizon,
    )

    # 2. Monte Carlo empirical frequency
    simulator = QueueMonteCarloSimulator(
        trade_intensity=trade_rate,
        cancellation_intensity=cancel_rate,
        mean_trade_size=1.0,
        mean_cancel_size=1.0,
        cancellation_model=CancellationModel.PROPORTIONAL,
        seed=1337,
    )

    res = simulator.evaluate(
        initial_ahead_volume=ahead_vol,
        order_quantity=order_qty,
        horizon_sec=horizon,
        num_trials=2_000,
    )

    # Validate that empirical fill probability aligns closely with analytical bounds
    np.testing.assert_allclose(res.empirical_fill_probability, prob_analytical, atol=0.15)
    assert res.mean_time_to_fill <= horizon


def test_tail_skewed_cancellation_preserves_ahead_volume():
    ahead_vol = 50.0
    order_qty = 10.0
    horizon = 3.0

    # Under tail-skewed cancellations, orders ahead cancel much slower
    sim_skewed = QueueMonteCarloSimulator(
        trade_intensity=5.0,
        cancellation_intensity=25.0,
        cancellation_model=CancellationModel.TAIL_SKEWED,
        seed=42,
    )
    res_skewed = sim_skewed.evaluate(ahead_vol, order_qty, horizon, num_trials=500)

    # Under proportional cancellations, ahead volume drops faster
    sim_prop = QueueMonteCarloSimulator(
        trade_intensity=5.0,
        cancellation_intensity=25.0,
        cancellation_model=CancellationModel.PROPORTIONAL,
        seed=42,
    )
    res_prop = sim_prop.evaluate(ahead_vol, order_qty, horizon, num_trials=500)

    # Tail-skewed must yield lower or equal fill rate since front orders are stickier
    assert res_skewed.empirical_fill_probability <= res_prop.empirical_fill_probability + 0.05
