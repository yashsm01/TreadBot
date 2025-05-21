from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
from app.core.database import get_db
from app.services.one_inch_service import one_inch_service

router = APIRouter()

@router.get("/tokens/{chain_id}", response_model=Dict)
async def get_tokens(
    chain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all tokens supported by 1inch on a specific chain"""
    try:
        return await one_inch_service.get_tokens(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/token/{chain_id}/{token_address}", response_model=Dict)
async def get_token(
    chain_id: int,
    token_address: str,
    db: AsyncSession = Depends(get_db)
):
    """Get token info for a specific token address"""
    try:
        token = await one_inch_service.get_token_by_address(chain_id, token_address)
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
        return token
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quote/{chain_id}", response_model=Dict)
async def get_quote(
    chain_id: int,
    from_token_address: str,
    to_token_address: str,
    amount: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a quote for swapping tokens"""
    try:
        return await one_inch_service.get_quote(
            chain_id=chain_id,
            from_token=from_token_address,
            to_token=to_token_address,
            amount=amount
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/swap/{chain_id}", response_model=Dict)
async def get_swap(
    chain_id: int,
    from_token_address: str,
    to_token_address: str,
    amount: str,
    from_address: str,
    slippage: float = 1.0,  # Default slippage 1%
    db: AsyncSession = Depends(get_db)
):
    """Get swap data for executing a swap transaction"""
    try:
        return await one_inch_service.get_swap(
            chain_id=chain_id,
            from_token=from_token_address,
            to_token=to_token_address,
            amount=amount,
            from_address=from_address,
            slippage=slippage
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/protocols/{chain_id}", response_model=Dict)
async def get_protocols(
    chain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all protocols supported by 1inch on a specific chain"""
    try:
        return await one_inch_service.get_protocols(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/healthcheck/{chain_id}", response_model=Dict)
async def get_healthcheck(
    chain_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Check the health of the 1inch API for a specific chain"""
    try:
        return await one_inch_service.get_healthcheck(chain_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
