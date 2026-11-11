"""Analytical fill probability estimators conditioned on queue position and flow rates."""

import numpy as np
from scipy.stats import norm


class FillProbabilityEstimator:
    """Estimates execution probability of resting orders before adverse price moves."""

    @staticmethod
    def estimate_poisson_fill_prob(
        ahead_volume: float,
        order_quantity: float,
        trade_intensity: float,
        cancellation_intensity: float,
        horizon_sec: float,
    ) -> float:
        """
        Continuous approximation of fill probability under Poisson arrival of trades and cancels.
        mu_depletion = trade_intensity + cancellation_intensity (rate of ahead volume clearing)
        """
        if ahead_volume <= 0:
            return 1.0
        if horizon_sec <= 0 or (trade_intensity <= 0 and cancellation_intensity <= 0):
            return 0.0

        required_clearance = ahead_volume + order_quantity
        effective_depletion_rate = trade_intensity + (0.5 * cancellation_intensity)

        expected_cleared = effective_depletion_rate * horizon_sec
        # Diffusion approximation variance
        variance = (trade_intensity + cancellation_intensity) * horizon_sec

        if variance <= 1e-9:
            return 1.0 if expected_cleared >= required_clearance else 0.0

        std_dev = np.sqrt(variance)
        # Z-score for clearing required volume before horizon
        z = (expected_cleared - required_clearance) / std_dev
        prob = float(norm.cdf(z))
        return min(max(prob, 0.0), 1.0)
