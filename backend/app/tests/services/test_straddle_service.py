import pytest
from datetime import datetime
import pandas as pd
from unittest.mock import Mock, patch
from app.services.straddle_service import StraddleService, StraddleStrategy
from app.schemas.trade import TradeCreate
from app.models.trade import Trade
from app.services.helper.market_analyzer import BreakoutSignal

@pytest.fixture
def db_session():
    return Mock()

@pytest.fixture
def straddle_service(db_session):
    return StraddleService(db_session)

class TestStraddleStrategy:
    def test_calculate_entry_levels(self):
        strategy = StraddleStrategy()
        current_price = 100.0
        buy_entry, sell_entry = strategy.calculate_entry_levels(current_price)

        assert buy_entry == current_price * 1.01
        assert sell_entry == current_price * 0.99

    def test_calculate_position_params(self):
        strategy = StraddleStrategy()
        entry_price = 100.0

        # Test UP direction
        tp_up, sl_up = strategy.calculate_position_params(entry_price, "UP")
        assert tp_up > entry_price
        assert sl_up < entry_price

        # Test DOWN direction
        tp_down, sl_down = strategy.calculate_position_params(entry_price, "DOWN")
        assert tp_down < entry_price
        assert sl_down > entry_price

class TestStraddleService:
    @pytest.mark.asyncio
    async def test_analyze_market_conditions(self, straddle_service):
        symbol = "BTC/USDT"
        prices = pd.Series([100, 101, 102, 103, 104])
        volume = pd.Series([1000, 1100, 1200, 1300, 1400])

        with patch('app.services.helper.market_analyzer.market_analyzer.analyze_breakout') as mock_analyze:
            mock_analyze.return_value = BreakoutSignal(
                direction="UP",
                price=104.0,
                confidence=0.8,
                volume_spike=True,
                rsi_divergence=True,
                macd_crossover=True
            )

            result = await straddle_service.analyze_market_conditions(symbol, prices, volume)
            assert result.direction == "UP"
            assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_create_straddle_trades(self, straddle_service):
        symbol = "BTC/USDT"
        current_price = 100.0
        quantity = 1.0

        # Mock the trade creation in database
        mock_trade = Trade(
            id=1,
            symbol=symbol,
            side="BUY",
            entry_price=101.0,
            quantity=quantity,
            status="PENDING"
        )

        with patch('app.crud.crud_trade.trade.create') as mock_create:
            mock_create.return_value = mock_trade

            with patch('app.services.notifications.notification_service.send_straddle_setup_notification') as mock_notify:
                trades = await straddle_service.create_straddle_trades(symbol, current_price, quantity)

                assert len(trades) == 2
                assert trades[0].side == "BUY"
                assert trades[1].side == "SELL"
                assert mock_notify.called

    @pytest.mark.asyncio
    async def test_handle_breakout(self, straddle_service):
        symbol = "BTC/USDT"
        breakout_signal = BreakoutSignal(
            direction="UP",
            price=105.0,
            confidence=0.85,
            volume_spike=True,
            rsi_divergence=True,
            macd_crossover=True
        )

        mock_trades = [
            Trade(id=1, symbol=symbol, side="BUY", status="PENDING"),
            Trade(id=2, symbol=symbol, side="SELL", status="PENDING")
        ]

        with patch('app.crud.crud_trade.trade.get_multi_by_symbol_and_status') as mock_get:
            mock_get.return_value = mock_trades

            with patch('app.crud.crud_trade.trade.update') as mock_update:
                mock_update.return_value = mock_trades[0]

                with patch('app.services.notifications.notification_service.send_breakout_notification') as mock_notify:
                    result = await straddle_service.handle_breakout(symbol, breakout_signal)

                    assert result.side == "BUY"
                    assert mock_notify.called

    @pytest.mark.asyncio
    async def test_close_straddle_trades(self, straddle_service):
        symbol = "BTC/USDT"
        mock_trades = [
            Trade(
                id=1,
                symbol=symbol,
                side="BUY",
                status="OPEN",
                entry_price=100.0,
                exit_price=105.0,
                pnl=5.0
            )
        ]

        with patch('app.crud.crud_trade.trade.get_multi_by_symbol_and_status') as mock_get:
            mock_get.return_value = mock_trades

            with patch('app.crud.crud_trade.trade.update') as mock_update:
                mock_update.return_value = mock_trades[0]

                with patch('app.services.notifications.notification_service.send_position_close_notification') as mock_notify:
                    closed_trades = await straddle_service.close_straddle_trades(symbol)

                    assert len(closed_trades) == 1
                    assert closed_trades[0].status == "CLOSED"
                    assert mock_notify.called
