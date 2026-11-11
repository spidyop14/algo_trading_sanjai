from sqlalchemy import select
from strategy.models.strategy_config import StrategyConfiguration

class StrategyManager:
    def __init__(self, session): self.session = session
    def get_or_create(self, name="EMA crossover"):
        config = self.session.scalar(select(StrategyConfiguration).where(StrategyConfiguration.name == name))
        if not config: config = StrategyConfiguration(name=name); self.session.add(config); self.session.flush()
        return config
    def enabled(self): return list(self.session.scalars(select(StrategyConfiguration).where(StrategyConfiguration.enabled.is_(True))))
