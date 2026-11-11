from backend.providers.simulated_provider import SimulatedNSEProvider

class MarketService:
    def __init__(self): self.provider = SimulatedNSEProvider()
    def scanner(self): return [self.provider.quote(symbol) for symbol in self.provider._prices]
    def health(self): return {"provider": "SIMULATED", "connected": True, "live": False}
