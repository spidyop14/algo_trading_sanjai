def crossover(previous_fast, previous_slow, current_fast, current_slow) -> int:
    if any(value is None for value in (previous_fast, previous_slow, current_fast, current_slow)): return 0
    if previous_fast <= previous_slow and current_fast > current_slow: return 1
    if previous_fast >= previous_slow and current_fast < current_slow: return -1
    return 0

def risk_levels(action: str, entry: float, atr_value: float, atr_multiplier: float = 1.5, risk_reward: float = 2.0, stop_mode: str = "ATR", fixed_stop_pct: float = 1.0):
    risk = entry * fixed_stop_pct / 100 if stop_mode == "FIXED" else atr_value * atr_multiplier
    if risk <= 0: raise ValueError("Risk distance must be positive")
    if action == "BUY": stop, target = entry - risk, entry + risk * risk_reward
    elif action == "SELL": stop, target = entry + risk, entry - risk * risk_reward
    else: raise ValueError("Risk levels require BUY or SELL")
    if stop <= 0 or target <= 0: raise ValueError("Invalid stop or target")
    return round(stop, 2), round(target, 2), round(risk_reward, 2)

def trailing_stop(action: str, prior_stop: float, current_price: float, atr_value: float, multiplier: float = 1.5) -> float:
    candidate = current_price - atr_value * multiplier if action == "BUY" else current_price + atr_value * multiplier
    return max(prior_stop, candidate) if action == "BUY" else min(prior_stop, candidate)
