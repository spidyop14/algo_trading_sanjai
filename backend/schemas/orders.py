from dataclasses import dataclass
from backend.database.models import OrderSide, OrderType
from backend.core.exceptions import ValidationError


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: float | None = None

    def validate(self) -> None:
        if not self.symbol or not self.symbol.isalnum() or len(self.symbol) > 30: raise ValidationError("Invalid NSE symbol")
        if self.quantity <= 0: raise ValidationError("Quantity must be positive")
        if self.order_type == OrderType.LIMIT and (self.limit_price is None or self.limit_price <= 0): raise ValidationError("Limit price is required for limit orders")
