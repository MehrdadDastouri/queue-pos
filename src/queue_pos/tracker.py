"""Core deterministic queue position tracker driven by market data updates."""

from typing import Dict, List, Optional, Tuple
from queue_pos.models import CancellationModel, OrderQueueStatus, Side, TrackedOrder


class QueuePositionTracker:
    """Tracks queue progress and depletes ahead/behind volumes deterministically."""

    def __init__(self, cancellation_model: CancellationModel = CancellationModel.PROPORTIONAL) -> None:
        self.cancellation_model = cancellation_model
        self._orders: Dict[int, TrackedOrder] = {}

    def track_order(
        self,
        order_id: int,
        side: Side,
        price: float,
        quantity: float,
        current_level_volume: float,
    ) -> TrackedOrder:
        """
        Register a new passive limit order placed at the tail of the existing queue.
        current_level_volume represents existing depth before this order rests.
        """
        ahead_volume = max(0.0, current_level_volume)
        tracked = TrackedOrder(
            order_id=order_id,
            side=side,
            price=price,
            original_quantity=quantity,
            remaining_quantity=quantity,
            ahead_volume=ahead_volume,
            behind_volume=0.0,
            status=OrderQueueStatus.PENDING,
        )
        self._orders[order_id] = tracked
        return tracked

    def on_trade(self, price: float, side: Side, volume: float) -> List[Tuple[int, float]]:
        """
        Process aggressive trade print executing at given price.
        side corresponds to the passive maker side being consumed.
        Returns list of (order_id, filled_volume) for our orders that executed.
        """
        fills: List[Tuple[int, float]] = []

        for order in self._orders.values():
            if order.status in (OrderQueueStatus.FILLED, OrderQueueStatus.CANCELLED):
                continue
            if order.price != price or order.side != side:
                continue

            # Trade strictly eats from the head of the queue (ahead_volume)
            if order.ahead_volume > 0:
                consumed = min(order.ahead_volume, volume)
                order.ahead_volume -= consumed
                unconsumed_trade = volume - consumed
            else:
                unconsumed_trade = volume

            # If ahead volume is fully exhausted, trade executes our resting size
            if unconsumed_trade > 0 and order.remaining_quantity > 0:
                fill_qty = min(order.remaining_quantity, unconsumed_trade)
                order.remaining_quantity -= fill_qty
                fills.append((order.order_id, fill_qty))

                if order.remaining_quantity == 0:
                    order.status = OrderQueueStatus.FILLED
                else:
                    order.status = OrderQueueStatus.PARTIALLY_FILLED

        return fills

    def on_level_volume_update(self, price: float, side: Side, new_total_volume: float) -> None:
        """
        Reconcile queue state against L2 incremental level updates.
        Handles passive additions and external cancellations.
        """
        for order in self._orders.values():
            if order.status in (OrderQueueStatus.FILLED, OrderQueueStatus.CANCELLED):
                continue
            if order.price != price or order.side != side:
                continue

            current_est_total = order.total_level_volume
            volume_delta = new_total_volume - current_est_total

            if volume_delta > 0:
                # Fresh liquidity enters exclusively behind our resting priority
                order.behind_volume += volume_delta
            elif volume_delta < 0:
                # Cancellation occurred somewhere in the queue
                cancel_size = abs(volume_delta)
                self._apply_cancellation(order, cancel_size)

    def _apply_cancellation(self, order: TrackedOrder, cancel_size: float) -> None:
        """Distribute external cancellations between ahead and behind queues."""
        other_volume = order.ahead_volume + order.behind_volume
        if other_volume <= 0:
            return

        if self.cancellation_model == CancellationModel.PROPORTIONAL:
            ahead_share = order.ahead_volume / other_volume
            ahead_cancel = min(order.ahead_volume, cancel_size * ahead_share)
            behind_cancel = min(order.behind_volume, cancel_size - ahead_cancel)

            order.ahead_volume -= ahead_cancel
            order.behind_volume -= behind_cancel

        elif self.cancellation_model == CancellationModel.TAIL_SKEWED:
            behind_capacity = order.behind_volume
            assigned_behind = min(behind_capacity, cancel_size * 0.8)
            residual_cancel = cancel_size - assigned_behind

            ahead_cancel = min(order.ahead_volume, residual_cancel)
            order.behind_volume -= assigned_behind
            order.ahead_volume -= ahead_cancel

    def get_order(self, order_id: int) -> Optional[TrackedOrder]:
        return self._orders.get(order_id)
