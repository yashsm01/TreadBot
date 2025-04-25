from fastapi import APIRouter
from app.api.v1.endpoints import trades, positions, strategy

api_router = APIRouter()

api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(positions.router, prefix="/positions", tags=["positions"])
api_router.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
