from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.graph_service import get_price_and_swaps_for_chart, generate_price_swap_plot
from typing import Optional

router = APIRouter()

@router.get('/chart', response_class=HTMLResponse)
async def chart(
    symbol: str = Query(..., description='Crypto symbol, e.g. BTC/USDT'),
    month: Optional[int] = Query(None, description='Month (1-12)'),
    year: Optional[int] = Query(None, description='Year (e.g. 2024)'),
    duration: Optional[str] = Query('1m', description='Duration: 1d, 1w, 1m, 3m, 1y'),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns an interactive HTML chart of price and swap events for the given symbol and duration.
    """
    result = await get_price_and_swaps_for_chart(db, symbol=symbol, month=month, year=year, duration=duration)
    html_chart = generate_price_swap_plot(result)
    return html_chart
