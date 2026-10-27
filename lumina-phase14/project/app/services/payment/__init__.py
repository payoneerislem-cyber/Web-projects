"""Payment providers + registry."""
from app.services.payment.base import PaymentProvider, PaymentResult
from app.services.payment.cod import CashOnDeliveryProvider
from app.services.payment.demo import DemoProvider

_REGISTRY: dict = {}


def register(provider: PaymentProvider) -> None:
    _REGISTRY[provider.key] = provider


def get_provider(key: str) -> PaymentProvider:
    try:
        return _REGISTRY[key]
    except KeyError:
        raise KeyError(f"Unknown payment method: {key!r}") from None


def available_providers() -> list:
    return list(_REGISTRY.values())


register(CashOnDeliveryProvider())
register(DemoProvider())

__all__ = ["PaymentProvider", "PaymentResult", "available_providers", "get_provider", "register"]
