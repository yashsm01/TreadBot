from fastapi import APIRouter
from app.api.v1.endpoints import (
    trade_routes,
    analysis_routes,
    portfolio_routes,
    telegram_routes,
    crypto_routes,
    straddle_routes,
    swap_transaction_routes
)

api_router = APIRouter()

# Include all routers with their prefixes and tags
api_router.include_router(
    trade_routes.router,
    prefix="/trades",
    tags=["trades"]
)

api_router.include_router(
    analysis_routes.router,
    prefix="/analysis",
    tags=["analysis"]
)

api_router.include_router(
    portfolio_routes.router,
    prefix="/portfolio",
    tags=["portfolio"]
)

api_router.include_router(
    telegram_routes.router,
    prefix="/telegram",
    tags=["telegram"]
)

# Include straddle endpoints
api_router.include_router(
    straddle_routes.router,
    prefix="/straddle",
    tags=["straddle"]
)

# Include crypto table endpoints
api_router.include_router(
    crypto_routes.router,
    prefix="/crypto",
    tags=["crypto"]
)

# Include swap transaction endpoints
api_router.include_router(
    swap_transaction_routes.router,
    prefix="/swap-transactions",
    tags=["swap-transactions"]
)
