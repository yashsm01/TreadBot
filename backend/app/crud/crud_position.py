from typing import List, Optional
from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models.position import Position
from app.schemas.position import PositionCreate, PositionUpdate

class CRUDPosition(CRUDBase[Position, PositionCreate, PositionUpdate]):
    def get_by_symbol(
        self, db: Session, *, symbol: str, skip: int = 0, limit: int = 100
    ) -> List[Position]:
        return (
            db.query(self.model)
            .filter(Position.symbol == symbol)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_active_positions(
        self, db: Session, *, symbol: Optional[str] = None
    ) -> List[Position]:
        query = db.query(self.model).filter(Position.status == "ACTIVE")
        if symbol:
            query = query.filter(Position.symbol == symbol)
        return query.all()

    def get_by_strategy(
        self, db: Session, *, strategy: str, skip: int = 0, limit: int = 100
    ) -> List[Position]:
        return (
            db.query(self.model)
            .filter(Position.strategy == strategy)
            .offset(skip)
            .limit(limit)
            .all()
        )

position = CRUDPosition(Position)
