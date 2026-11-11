from sqlalchemy import select
from backend.database.models import Position
from backend.database.repositories import get_or_create_paper_account
from backend.providers.simulated_provider import SimulatedNSEProvider
from backend.schemas.positions import PositionView


class PositionService:
    def __init__(self, session): self.session = session; self.provider = SimulatedNSEProvider()
    def list(self):
        account = get_or_create_paper_account(self.session)
        rows = self.session.scalars(select(Position).where(Position.account_id == account.id, Position.quantity != 0))
        return [PositionView(p.symbol, p.quantity, p.average_entry_price, self.provider.quote(p.symbol).price, p.quantity * self.provider.quote(p.symbol).price, (self.provider.quote(p.symbol).price - p.average_entry_price) * p.quantity, p.realised_pnl) for p in rows]
