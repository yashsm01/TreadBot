from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import validates
from ..database import Base
import re

class Cryptocurrency(Base):
    __tablename__ = "cryptocurrencies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)  # e.g., "BTC/USDT"
    name = Column(String, nullable=False)  # e.g., "Bitcoin"
    is_active = Column(Boolean, default=True, nullable=False)
    min_quantity = Column(Float, nullable=False)  # Minimum trade quantity
    price_precision = Column(Integer, nullable=False)  # Number of decimal places for price
    quantity_precision = Column(Integer, nullable=False)  # Number of decimal places for quantity
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Add constraints
    __table_args__ = (
        CheckConstraint('min_quantity > 0', name='check_min_quantity_positive'),
        CheckConstraint('price_precision >= 0', name='check_price_precision_non_negative'),
        CheckConstraint('quantity_precision >= 0', name='check_quantity_precision_non_negative'),
    )

    @validates('symbol')
    def validate_symbol(self, key, symbol):
        """Validate trading pair symbol format"""
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        # Check format (e.g., BTC/USDT)
        if not re.match(r'^[A-Z0-9]+/[A-Z0-9]+$', symbol):
            raise ValueError("Symbol must be in format BASE/QUOTE (e.g., BTC/USDT)")

        return symbol

    @validates('name')
    def validate_name(self, key, name):
        """Validate cryptocurrency name"""
        if not name or len(name.strip()) == 0:
            raise ValueError("Name cannot be empty")
        return name.strip()

    @validates('min_quantity', 'price_precision', 'quantity_precision')
    def validate_numeric_fields(self, key, value):
        """Validate numeric fields"""
        if value is None:
            raise ValueError(f"{key} cannot be None")

        if key == 'min_quantity' and value <= 0:
            raise ValueError("Minimum quantity must be positive")
        elif (key in ['price_precision', 'quantity_precision']) and value < 0:
            raise ValueError(f"{key} cannot be negative")

        return value

    def format_price(self, price):
        """Format price according to precision"""
        return round(float(price), self.price_precision)

    def format_quantity(self, quantity):
        """Format quantity according to precision"""
        return round(float(quantity), self.quantity_precision)

    def validate_trade_quantity(self, quantity):
        """Validate if trade quantity meets minimum requirement"""
        if float(quantity) < self.min_quantity:
            raise ValueError(f"Quantity {quantity} is below minimum {self.min_quantity}")
        return True

    def __repr__(self):
        return f"<Cryptocurrency(symbol={self.symbol}, name={self.name})>"

    def to_dict(self):
        """Convert model to dictionary with formatted values"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "is_active": self.is_active,
            "min_quantity": float(self.min_quantity),  # Ensure float format
            "price_precision": self.price_precision,
            "quantity_precision": self.quantity_precision,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
