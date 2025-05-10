from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.curd_crypto import create_crypto_table, table_exists, sanitize_table_name, insert_crypto_data, insert_crypto_data_live
from app.core.database import get_db
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime

router = APIRouter()

class TableCreateRequest(BaseModel):
    symbol: str
    month: Optional[int] = Field(None, ge=1, le=12, description="Month (1-12)")
    year: Optional[int] = Field(None, ge=2000, le=2100, description="Year (e.g., 2025)")

class TableResponse(BaseModel):
    symbol: str
    table_name: str
    month: Optional[int] = None
    year: Optional[int] = None
    success: bool
    message: str

class CryptoDataInsertRequest(BaseModel):
    symbol: str
    month: Optional[int] = Field(None, ge=1, le=12, description="Month (1-12)")
    year: Optional[int] = Field(None, ge=2000, le=2100, description="Year (e.g., 2025)")
    current_price: float = Field(..., gt=0, description="Current price of the cryptocurrency")
    name: Optional[str] = None
    timestamp: Optional[datetime] = None

    @validator('timestamp', pre=True, always=True)
    def set_timestamp(cls, v):
        return v or datetime.now()

class DataInsertResponse(BaseModel):
    symbol: str
    table_name: str
    month: int
    year: int
    success: bool
    message: str

@router.post("/tables/create", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    request: TableCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new cryptocurrency table for the specified trading pair with optional month/year format
    """
    try:
        # Set default month/year if not provided
        month = request.month
        year = request.year

        if month is None or year is None:
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # Call the function to create the table
        success = await create_crypto_table(db, request.symbol, month, year)

        # Create sanitized table name for response
        sanitized_name = sanitize_table_name(request.symbol, month, year)

        if success:
            return TableResponse(
                symbol=request.symbol,
                table_name=sanitized_name,
                month=month,
                year=year,
                success=True,
                message=f"Table for {request.symbol} ({month:02d}/{year}) created successfully"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create table for {request.symbol}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating table: {str(e)}"
        )

@router.get("/tables/check/{symbol}")
async def check_table_exists(
    symbol: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Check if a table exists for the specified trading pair with optional month/year format
    """
    try:
        # Set default month/year if not provided
        if month is None or year is None:
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # Validate month and year
        if not (1 <= month <= 12) or not (2000 <= year <= 2100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid month ({month}) or year ({year})"
            )

        # Sanitize the symbol for table name
        sanitized_name = sanitize_table_name(symbol, month, year)

        # Check if the table exists
        exists = await table_exists(db, sanitized_name)

        return TableResponse(
            symbol=symbol,
            table_name=sanitized_name,
            month=month,
            year=year,
            success=exists,
            message=f"Table for {symbol} ({month:02d}/{year}) {'exists' if exists else 'does not exist'}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking table: {str(e)}"
        )

@router.post("/data/insert", response_model=DataInsertResponse)
async def insert_data(
    request: CryptoDataInsertRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Insert cryptocurrency data into the corresponding table
    """
    try:
        # Normalize symbol
        symbol = request.symbol.strip().upper()

        # Set default month/year if not provided
        month = request.month
        year = request.year

        if month is None or year is None:
            now = datetime.now()
            month = month or now.month
            year = year or now.year

        # Prepare data dictionary
        data = {
            "current_price": request.current_price,
            "name": request.name or symbol,
            "timestamp": request.timestamp,
            "created_at": datetime.now()
        }

        # Get table name for response
        table_name = sanitize_table_name(symbol, month, year)

        # Call the function to insert data
        success = await insert_crypto_data(db, symbol, data, month, year)

        if success:
            return DataInsertResponse(
                symbol=symbol,
                table_name=table_name,
                month=month,
                year=year,
                success=True,
                message=f"Data for {symbol} inserted successfully into {table_name}"
            )
        else:
            # Check if table exists, if not create it first
            table_exists_result = await table_exists(db, table_name)

            if not table_exists_result:
                # Table doesn't exist, try to create it
                create_result = await create_crypto_table(db, symbol, month, year)

                if create_result:
                    # Try to insert data again
                    retry_success = await insert_crypto_data(db, symbol, data, month, year)

                    if retry_success:
                        return DataInsertResponse(
                            symbol=symbol,
                            table_name=table_name,
                            month=month,
                            year=year,
                            success=True,
                            message=f"Table {table_name} created and data inserted successfully"
                        )

            # If we get here, insertion failed
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to insert data for {symbol}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inserting data: {str(e)}"
        )

@router.get("/live/insert")
async def insert_live_data(
    db: AsyncSession = Depends(get_db)
):
    """
    Insert Live cryptocurrency data into the corresponding table
    """
    try:
        #static array of symbols
        symbols = ["BTC/USDT", "ETH/USDT","GUN/USDT"]
        for symbol in symbols:
            result = await insert_crypto_data_live(db, symbol);
            print(result)
        return(result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error inserting data: {str(e)}"
        )
