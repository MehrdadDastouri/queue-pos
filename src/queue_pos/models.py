"""Domain models for queue tracking, order states, and cancellation modes."""

from dataclasses import dataclass
from enum import IntEnum


class Side(IntEnum):
    """Trading side."""
    BID = 1
    ASK = -1


class CancellationModel(IntEnum):
    """Assumed distribution of cancellations across the queue."""
    PROPORTIONAL = 1  # Uniform proportional attrition
    TAIL_SKEWED = 2   # High cancellation hazard towards the tail of the queue


class OrderQueueStatus(IntEnum):
    """Lifecycle state of an order inside the priority queue."""
    PENDING = 1
    PARTIALLY_FILLED = 2
    FILLED = 3
    CANCELLED = 4


@dataclass(slots=True)
class TrackedOrder:
    """Internal state representation of our passive order inside the queue."""
    order_id: int
    side: Side
    price: float
    original_quantity: float
    remaining_quantity: float
    ahead_volume: float
    behind_volume: float
    status: OrderQueueStatus = OrderQueueStatus.PENDING

    @property
    def total_level_volume(self) -> float:
        """Total estimated volume at the price level containing this order."""
        return self.ahead_volume + self.remaining_quantity + self.behind_volume

    @property
    def relative_position(self) -> float:
        """Normalized position in queue from 0.0 (front) to 1.0 (very back)."""
        total = self.total_level_volume
        if total <= 0.0:
            return 0.0
        return self.ahead_volume / total
