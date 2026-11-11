import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.instrument import Instrument


class InstrumentService:
    def __init__(self, session: Session): self.session = session
    def import_master(self, path: str | Path) -> int:
        imported = 0
        with Path(path).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                symbol = row["trading_symbol"].upper(); exchange = row.get("exchange", "NSE")
                item = self.session.scalar(select(Instrument).where(Instrument.trading_symbol == symbol, Instrument.exchange == exchange))
                values = {"company_name": row["company_name"], "sector": row.get("sector", "Unclassified"), "instrument_type": row.get("instrument_type", "EQ"), "universe": row.get("universe", ""), "instrument_token": int(row["instrument_token"]) if row.get("instrument_token") else None}
                if item:
                    for key, value in values.items(): setattr(item, key, value)
                else: self.session.add(Instrument(trading_symbol=symbol, exchange=exchange, **values))
                imported += 1
        self.session.flush(); return imported
    def list(self, universe: str | None = None) -> list[Instrument]:
        query = select(Instrument).order_by(Instrument.trading_symbol)
        if universe: query = query.where(Instrument.universe.like(f"%{universe}%"))
        return list(self.session.scalars(query))
