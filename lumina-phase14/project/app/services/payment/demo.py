import secrets

from app.services.payment.base import PaymentProvider, PaymentResult


class DemoProvider(PaymentProvider):
    """Fake gateway for local development: pick approve/decline, no card data involved."""

    key = "demo_card"
    label = "Demo card (test payment)"
    description = "Simulated card payment. No real money moves."
    test_mode = True

    def charge(self, order, payload: dict) -> PaymentResult:
        if (payload or {}).get("scenario") == "decline":
            return PaymentResult(False, "failed", None, "The demo card was declined. Try a different payment method.")
        return PaymentResult(True, "paid", f"DEMO-{secrets.token_hex(5).upper()}", "Payment approved.")
