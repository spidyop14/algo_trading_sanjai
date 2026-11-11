from backend.database.repositories import get_or_create_paper_account
from backend.trading.order_manager import OrderManager
from backend.providers.simulated_provider import SimulatedNSEProvider


class OrderService:
    def __init__(self, session): self.session = session; self.manager = OrderManager(session, SimulatedNSEProvider())
    def place(self, request): return self.manager.place(get_or_create_paper_account(self.session).id, request)
    def cancel(self, order_id): return self.manager.cancel(order_id)
