from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from app.crud.curd_crypto import sanitize_table_name
from typing import List, Dict, Any, Optional
import logging
import plotly.graph_objects as go
import pandas as pd

logger = logging.getLogger(__name__)

DURATION_MAP = {
    '1d': timedelta(days=1),
    '1w': timedelta(weeks=1),
    '1m': timedelta(days=30),
    '3m': timedelta(days=90),
    '1y': timedelta(days=365),
}

def get_time_range_for_duration(duration: str) -> (datetime, datetime):
    """
    Returns (start_time, end_time) for a given duration string.
    """
    now = datetime.now()
    delta = DURATION_MAP.get(duration, timedelta(days=30))
    return now - delta, now

async def get_price_and_swaps_for_chart(
    db: AsyncSession,
    symbol: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    duration: Optional[str] = None,
    limit: int = 5000
) -> Dict[str, Any]:
    """
    Fetch price data from the dynamic crypto table and swap transactions for a given symbol and time range.
    Returns a dict with price points and swap events for charting.
    Supports duration strings like '1d', '1w', '1m', '3m', '1y'.
    """
    table_name = sanitize_table_name(symbol, month, year)
    if duration and not (start_time or end_time):
        start_time, end_time = get_time_range_for_duration(duration)
    time_filter = ""
    params = {}
    if start_time:
        time_filter += " AND p.timestamp >= :start_time"
        params['start_time'] = start_time
    if end_time:
        time_filter += " AND p.timestamp <= :end_time"
        params['end_time'] = end_time
    price_query = text(f'''
        SELECT
            p.timestamp,
            p.current_price,
            p.swap_transactions_id,
            s.transaction_id,
            s.from_symbol,
            s.to_symbol,
            s.from_amount,
            s.to_amount,
            s.rate,
            s.fee_amount,
            s.realized_profit,
            s.status
        FROM "{table_name}" p
        LEFT JOIN swap_transactions s
            ON p.swap_transactions_id = s.transaction_id
        WHERE 1=1 {time_filter}
        ORDER BY p.timestamp ASC
        LIMIT :limit
    ''')
    params['limit'] = limit
    price_result = await db.execute(price_query, params)
    rows = price_result.fetchall()
    price_points = []
    swap_events = []
    for row in rows:
        price_points.append({
            'timestamp': row['timestamp'],
            'price': float(row['current_price']),
            'swap_transaction_id': row['swap_transactions_id']
        })
        if row['transaction_id']:
            swap_events.append({
                'timestamp': row['timestamp'],
                'transaction_id': row['transaction_id'],
                'from_symbol': row['from_symbol'],
                'to_symbol': row['to_symbol'],
                'from_amount': row['from_amount'],
                'to_amount': row['to_amount'],
                'rate': row['rate'],
                'fee_amount': row['fee_amount'],
                'realized_profit': row['realized_profit'],
                'status': row['status']
            })
    return {
        'price_points': price_points,
        'swap_events': swap_events
    }

def generate_price_swap_plot(result: dict) -> str:
    """
    Generate an interactive Plotly HTML chart for price and swap events.
    Returns HTML string to embed in web or return from FastAPI.
    """
    price_df = pd.DataFrame(result['price_points'])
    swap_df = pd.DataFrame(result['swap_events'])
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp'])
    if not swap_df.empty:
        swap_df['timestamp'] = pd.to_datetime(swap_df['timestamp'])
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=price_df['timestamp'],
        y=price_df['price'],
        mode='lines',
        name='Price',
        line=dict(color='blue')
    ))
    if not swap_df.empty:
        swap_prices = []
        for t in swap_df['timestamp']:
            idx = price_df['timestamp'].sub(t).abs().idxmin()
            swap_prices.append(price_df.loc[idx, 'price'])
        fig.add_trace(go.Scatter(
            x=swap_df['timestamp'],
            y=swap_prices,
            mode='markers',
            name='Swap',
            marker=dict(color='red', size=10, symbol='x'),
            text=[f"Swap: {tid}" for tid in swap_df['transaction_id']]
        ))
    fig.update_layout(
        title='Crypto Price with Swap Transactions',
        xaxis_title='Time',
        yaxis_title='Price',
        legend=dict(x=0, y=1)
    )
    return fig.to_html(full_html=False)
