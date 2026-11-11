from backend.database.repositories import get_or_create_paper_account
from backend.providers.simulated_provider import SimulatedNSEProvider
from backend.trading.portfolio_manager import PortfolioManager


class PortfolioService:
    def __init__(self, session): self.session = session; self.provider = SimulatedNSEProvider()
    def account(self): return get_or_create_paper_account(self.session)
    def summary(self): return PortfolioManager(self.session, self.provider).summary(self.account())
