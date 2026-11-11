"""Monte Carlo simulation harness for FIFO queue depletion and fill probability validation."""

from dataclasses import dataclass
from typing import Tuple
import numpy as np
from queue_pos.models import CancellationModel, OrderQueueStatus, Side
from queue_pos.tracker import QueuePositionTracker


@dataclass(slots=True)
class SimulationResult:
    """Summary statistics of Monte Carlo queue execution paths."""
    empirical_fill_probability: float
    mean_time_to_fill: float
    partial_fill_rate: float
    trials: int


class QueueMonteCarloSimulator:
    """Simulates thousands of realization paths to estimate queue clearance empirical distribution."""

    def __init__(
        self,
        trade_intensity: float,
        cancellation_intensity: float,
        mean_trade_size: float = 2.0,
        mean_cancel_size: float = 3.0,
        cancellation_model: CancellationModel = CancellationModel.PROPORTIONAL,
        seed: int = 42,
    ) -> None:
        self.trade_intensity = trade_intensity
        self.cancellation_intensity = cancellation_intensity
        self.mean_trade_size = mean_trade_size
        self.mean_cancel_size = mean_cancel_size
        self.cancellation_model = cancellation_model
        self._rng = np.random.default_rng(seed)

    def run_trial(
        self,
        initial_ahead_volume: float,
        order_quantity: float,
        horizon_sec: float,
        price: float = 100.0,
    ) -> Tuple[bool, float, bool]:
        """
        Execute a single realization path.
        Returns: (is_filled, time_to_fill, is_partially_filled)
        """
        tracker = QueuePositionTracker(cancellation_model=self.cancellation_model)
        order = tracker.track_order(
            order_id=1,
            side=Side.BID,
            price=price,
            quantity=order_quantity,
            current_level_volume=initial_ahead_volume,
        )

        current_time = 0.0
        total_rate = self.trade_intensity + self.cancellation_intensity

        if total_rate <= 0:
            return False, horizon_sec, False

        while current_time < horizon_sec:
            # Draw next arrival interval
            dt = self._rng.exponential(1.0 / total_rate)
            current_time += dt

            if current_time > horizon_sec:
                break

            # Event selection: Trade vs Cancellation
            is_trade = self._rng.uniform(0.0, 1.0) < (self.trade_intensity / total_rate)

            if is_trade:
                trade_volume = self._rng.exponential(self.mean_trade_size)
                tracker.on_trade(price=price, side=Side.BID, volume=trade_volume)
            else:
                cancel_volume = self._rng.exponential(self.mean_cancel_size)
                current_depth = order.total_level_volume
                new_depth = max(order.remaining_quantity, current_depth - cancel_volume)
                tracker.on_level_volume_update(price=price, side=Side.BID, new_total_volume=new_depth)

            if order.status == OrderQueueStatus.FILLED:
                return True, current_time, True

        is_partially_filled = order.status == OrderQueueStatus.PARTIALLY_FILLED
        return False, horizon_sec, is_partially_filled

    def evaluate(
        self,
        initial_ahead_volume: float,
        order_quantity: float,
        horizon_sec: float,
        num_trials: int = 1_000,
    ) -> SimulationResult:
        """Run multiple Monte Carlo paths and compile empirical statistics."""
        fills = 0
        partial_fills = 0
        fill_times = []

        for _ in range(num_trials):
            is_filled, t_fill, is_partial = self.run_trial(
                initial_ahead_volume=initial_ahead_volume,
                order_quantity=order_quantity,
                horizon_sec=horizon_sec,
            )
            if is_filled:
                fills += 1
                fill_times.append(t_fill)
            elif is_partial:
                partial_fills += 1

        empirical_fill_prob = fills / num_trials
        mean_ttf = float(np.mean(fill_times)) if fill_times else horizon_sec
        partial_rate = partial_fills / num_trials

        return SimulationResult(
            empirical_fill_probability=empirical_fill_prob,
            mean_time_to_fill=mean_ttf,
            partial_fill_rate=partial_rate,
            trials=num_trials,
        )
