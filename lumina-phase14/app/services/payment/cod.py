from app.services.payment.base import PaymentProvider, PaymentResult


class CashOnDeliveryProvider(PaymentProvider):
    key = "cod"
    label = "Cash on Delivery"
    description = "Pay in cash when your order arrives."

    def charge(self, order, payload: dict) -> PaymentResult:
        # Nothing is collected yet: the order stays "pending" until delivery.
        return PaymentResult(True, "pending", f"COD-{order.order_number}", "Pay on delivery.")

    def refund(self, order) -> PaymentResult:
        if order.payment_status != "paid":
            return PaymentResult(True, "pending", None, "Nothing was collected, so nothing to refund.")
        return super().refund(order)
