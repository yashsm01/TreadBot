from typing import List, Optional
from sqlalchemy.orm import Session
from backend.app.crud.base import CRUDBase
from backend.app.models.trade import Trade
from backend.app.schemas.trade import TradeCreate, TradeUpdate

class CRUDTrade(CRUDBase[Trade, TradeCreate, TradeUpdate]):
    def get_by_position(
        self, db: Session, *, position_id: int, skip: int = 0, limit: int = 100
    ) -> List[Trade]:
        return (
            db.query(self.model)
            .filter(Trade.position_id == position_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_open_trades(
        self, db: Session, *, symbol: Optional[str] = None
    ) -> List[Trade]:
        query = db.query(self.model).filter(Trade.status == "OPEN")
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        return query.all()

trade = CRUDTrade(Trade)
