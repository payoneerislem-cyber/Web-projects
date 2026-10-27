"""The contract every payment gateway implements.

Checkout only ever talks to this interface, so adding Stripe or PayPal later means
writing one new subclass and registering it; nothing in checkout changes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaymentResult:
    success: bool
    status: str  # "paid" | "pending" | "failed" | "refunded"
    reference: str | None = None
    message: str = ""


class PaymentProvider(ABC):
    key: str = ""
    label: str = ""
    description: str = ""
    test_mode: bool = False  # True: the checkout page shows a "test outcome" chooser

    @abstractmethod
    def charge(self, order, payload: dict) -> PaymentResult:
        """Attempt to collect payment for `order`. `payload` holds provider-specific input
        (never raw card numbers: those must go to the gateway directly)."""

    def refund(self, order) -> PaymentResult:
        return PaymentResult(True, "refunded", f"REFUND-{order.order_number}", "Refund recorded.")
