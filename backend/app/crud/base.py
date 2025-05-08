from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy import update
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).
        """
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        result = await db.execute(select(self.model).filter(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[ModelType]:
        result = await db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, db: AsyncSession, *, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: ModelType,
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        try:
            # Try to encode the object
            try:
                obj_data = jsonable_encoder(db_obj)
            except Exception as encode_error:
                raise ValueError(f"Failed to encode object: {str(encode_error)}")

            # Process update data
            try:
                if isinstance(obj_in, dict):
                    update_data = obj_in
                else:
                    update_data = obj_in.dict(exclude_unset=True)
            except Exception as dict_error:
                raise ValueError(f"Failed to process update data: {str(dict_error)}")

            # Update fields
            try:
                for field in obj_data:
                    if field in update_data:
                        setattr(db_obj, field, update_data[field])
            except Exception as field_error:
                raise ValueError(f"Failed to update field: {str(field_error)}")

            # Database operations
            try:
                db.add(db_obj)
                await db.commit()
                await db.refresh(db_obj)
            except Exception as db_error:
                await db.rollback()
                raise ValueError(f"Database operation failed: {str(db_error)}")

            return db_obj

        except Exception as e:
            # Log the error with more context
            error_msg = f"Update failed for {self.model.__name__}: {str(e)}"
            print(f"Error in update: {error_msg}")  # For immediate debugging
            raise ValueError(error_msg)

    async def remove(self, db: AsyncSession, *, id: int) -> ModelType:
        result = await db.execute(select(self.model).filter(self.model.id == id))
        obj = result.scalar_one()
        await db.delete(obj)
        await db.commit()
        return obj
