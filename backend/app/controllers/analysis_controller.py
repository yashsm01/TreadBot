from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from backend.app.services.market_analyzer import market_analyzer
from backend.app.services.portfolio_service import portfolio_service
from backend.app.core.logger import logger

class AnalysisController:
    @staticmethod
    async def get_market_analysis(symbol: str) -> Dict:
        """Get comprehensive market analysis"""
        try:
            # Get market conditions
            market_conditions = await market_analyzer.check_market_conditions(symbol)

            # Get trading signals
            trading_signal = await market_analyzer.get_trading_signal(symbol)

            return {
                "market_conditions": market_conditions,
                "trading_signal": trading_signal,
                "timestamp": trading_signal["timestamp"]
            }
        except Exception as e:
            logger.error(f"Error in market analysis: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def get_portfolio_analysis(
        db: Session,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> Dict:
        """Get comprehensive portfolio analysis"""
        try:
            # Get portfolio summary
            summary = await portfolio_service.get_portfolio_summary(db)

            # Get position metrics
            positions = await portfolio_service.get_position_metrics(db, symbol)

            # Get trading performance
            performance = await portfolio_service.get_trading_performance(db, days)

            return {
                "portfolio_summary": summary,
                "position_metrics": positions,
                "trading_performance": performance,
                "timestamp": summary["timestamp"]
            }
        except Exception as e:
            logger.error(f"Error in portfolio analysis: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def check_trade_viability(
        db: Session,
        symbol: str,
        quantity: float,
        price: float
    ) -> Dict:
        """Check if a trade is viable based on risk management"""
        try:
            # Check risk limits
            risk_check = await portfolio_service.check_risk_limits(
                db, symbol, quantity, price
            )

            # Get market conditions
            market_conditions = await market_analyzer.check_market_conditions(symbol)

            # Get trading signal
            trading_signal = await market_analyzer.get_trading_signal(symbol)

            return {
                "risk_assessment": risk_check,
                "market_conditions": market_conditions,
                "trading_signal": trading_signal,
                "timestamp": risk_check["timestamp"]
            }
        except Exception as e:
            logger.error(f"Error checking trade viability: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

analysis_controller = AnalysisController()
