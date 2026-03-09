"""
Simulated Broker Module (S1.3)
==============================

Simulated exchange for trading simulation.
"""

from .simulated_broker import (
    FillModel,
    InstantFillModel,
    SlippageFillModel,
    FeeCalculator,
    SimulatedAccountState,
    SimulatedBrokerAdapter,
    SimulatedBrokerService,
    simulated_broker_service
)

__all__ = [
    "FillModel",
    "InstantFillModel",
    "SlippageFillModel",
    "FeeCalculator",
    "SimulatedAccountState",
    "SimulatedBrokerAdapter",
    "SimulatedBrokerService",
    "simulated_broker_service"
]

print("[SimulatedBroker] Module loaded - S1.3 Ready")
